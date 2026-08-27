from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import DefaultCursorPagination
from community.models import Participation, Post, PostComment, Recruitment
from community.serializers import (
    ParticipationSerializer,
    ParticipationStatusSerializer,
    PostCommentSerializer,
    PostListSerializer,
    PostSerializer,
    PostWriteSerializer,
    RecruitmentSerializer,
)
from community.services import (
    annotated_posts,
    cancel_participation,
    close_recruitment,
    create_comment,
    increment_view_count,
    join_recruitment,
    set_participation_status,
)


def _post_detail_data(request, pk) -> dict:
    return PostSerializer(
        annotated_posts(request.user).get(pk=pk), context={"request": request}
    ).data


def _get_post(pk) -> Post:
    return generics.get_object_or_404(Post.objects.select_related("user"), pk=pk)


def _get_recruitment(pk) -> Recruitment:
    """게시글 id 로 모집 정보. 자유글이거나 없는 글이면 404."""
    return generics.get_object_or_404(
        Recruitment.objects.select_related("post__user", "gym"), post_id=pk
    )


def _require_author(request, obj_user_id: int, message: str) -> None:
    if obj_user_id != request.user.id:
        raise PermissionDenied(message)


class OldestFirstPagination(DefaultCursorPagination):
    """댓글·참여자는 시간순(오래된 것부터)."""

    ordering = "created_at"


# --- 게시글 -------------------------------------------------------------------


@extend_schema(
    tags=["community"],
    parameters=[
        OpenApiParameter(
            "category", str, enum=Post.Category.values, description="free | recruit"
        ),
        OpenApiParameter("gym", int, description="관련 암장 id 필터"),
    ],
)
class PostListCreateView(generics.ListCreateAPIView):
    """게시글 목록(커서, 최신순) + 작성. 모집글은 recruitment 를 함께 받는다."""

    queryset = Post.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    filterset_fields = ("category", "gym")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PostWriteSerializer
        return PostListSerializer

    def get_queryset(self):
        return annotated_posts(self.request.user)

    @extend_schema(request=PostWriteSerializer, responses={201: PostSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = serializer.save()
        return Response(
            _post_detail_data(request, post.pk), status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["community"])
class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    """게시글 상세 — 조회 시 조회수 +1(작성자 제외). 수정/삭제는 작성자만."""

    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return PostWriteSerializer
        return PostSerializer

    def get_queryset(self):
        return annotated_posts(self.request.user)

    def get_object(self):
        post = super().get_object()
        if self.request.method in ("PATCH", "DELETE"):
            _require_author(
                self.request, post.user_id, "본인의 게시글만 수정·삭제할 수 있습니다."
            )
        return post

    def retrieve(self, request, *args, **kwargs):
        post = self.get_object()
        if post.user_id != request.user.id:
            increment_view_count(post)
            post.view_count += 1  # 응답에는 증가분 반영 (재조회 없이)
        return Response(self.get_serializer(post).data)

    @extend_schema(request=PostWriteSerializer, responses=PostSerializer)
    def partial_update(self, request, *args, **kwargs):
        post = self.get_object()
        serializer = self.get_serializer(post, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_post_detail_data(request, post.pk))


# --- 댓글 ---------------------------------------------------------------------


@extend_schema(tags=["community"])
class PostCommentListCreateView(generics.ListCreateAPIView):
    """게시글 댓글 목록(커서, 오래된 순) + 작성. 1단계 답글은 parent 로."""

    queryset = PostComment.objects.none()  # 스키마 생성용
    serializer_class = PostCommentSerializer
    pagination_class = OldestFirstPagination

    def get_post(self) -> Post:
        if not hasattr(self, "_post"):
            self._post = _get_post(self.kwargs["pk"])
        return self._post

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["post"] = self.get_post()
        return context

    def get_queryset(self):
        return PostComment.objects.filter(post=self.get_post()).select_related(
            "user__profile"
        )

    def perform_create(self, serializer):
        serializer.instance = create_comment(
            self.get_post(),
            self.request.user,
            serializer.validated_data["content"],
            serializer.validated_data.get("parent"),
        )


@extend_schema(tags=["community"])
class PostCommentDeleteView(generics.DestroyAPIView):
    """댓글 삭제 — 작성자만, soft delete (답글도 함께)."""

    serializer_class = PostCommentSerializer

    def get_object(self):
        post = _get_post(self.kwargs["pk"])
        comment = generics.get_object_or_404(
            PostComment, pk=self.kwargs["comment_id"], post=post
        )
        _require_author(
            self.request, comment.user_id, "본인의 댓글만 삭제할 수 있습니다."
        )
        return comment


# --- 모집 ---------------------------------------------------------------------


@extend_schema(
    tags=["community"], request=None, responses={201: ParticipationSerializer}
)
class RecruitmentJoinView(APIView):
    """참여 신청 — instant 즉시 승인 / approval 대기. 정원 초과·마감·중복은 400."""

    def post(self, request, pk):
        participation = join_recruitment(_get_recruitment(pk), request.user)
        participation.user = request.user
        return Response(
            ParticipationSerializer(participation).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["community"], request=None, responses={204: None})
class RecruitmentCancelView(APIView):
    """내 참여 취소 (soft). 참여 중이 아니면 404."""

    def delete(self, request, pk):
        cancel_participation(_get_recruitment(pk), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["community"])
class ParticipantListView(generics.ListAPIView):
    """참여자 목록 — 작성자는 전체 상태, 나머지는 approved 만."""

    queryset = Participation.objects.none()  # 스키마 생성용
    serializer_class = ParticipationSerializer
    pagination_class = OldestFirstPagination

    def get_queryset(self):
        recruitment = _get_recruitment(self.kwargs["pk"])
        queryset = Participation.objects.filter(recruitment=recruitment).select_related(
            "user__profile"
        )
        if recruitment.post.user_id != self.request.user.id:
            queryset = queryset.filter(status=Participation.Status.APPROVED)
        return queryset


@extend_schema(
    tags=["community"],
    request=ParticipationStatusSerializer,
    responses=ParticipationSerializer,
)
class ParticipantUpdateView(APIView):
    """작성자의 승인/거절. 승인으로 정원이 차면 자동 마감."""

    def patch(self, request, pk, user_id):
        recruitment = _get_recruitment(pk)
        _require_author(
            request, recruitment.post.user_id, "모집 작성자만 승인·거절할 수 있습니다."
        )
        serializer = ParticipationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participation = set_participation_status(
            recruitment, user_id, serializer.validated_data["status"]
        )
        if participation is None:
            raise NotFound("참여 신청을 찾을 수 없습니다.")
        participation = Participation.objects.select_related("user__profile").get(
            pk=participation.pk
        )
        return Response(ParticipationSerializer(participation).data)


@extend_schema(tags=["community"], request=None, responses=RecruitmentSerializer)
class RecruitmentCloseView(APIView):
    """작성자 수동 마감 → status=closed, on_recruitment_closed 훅."""

    def post(self, request, pk):
        recruitment = _get_recruitment(pk)
        _require_author(
            request, recruitment.post.user_id, "모집 작성자만 마감할 수 있습니다."
        )
        close_recruitment(recruitment)
        return Response(_post_detail_data(request, pk)["recruitment"])
