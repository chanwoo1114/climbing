from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from climbs.models import ClimbLog, ClimbLogComment
from climbs.serializers import (
    ClimbLogCommentSerializer,
    ClimbLogSerializer,
    ClimbLogWriteSerializer,
)
from climbs.services import (
    annotated_logs,
    create_comment,
    feed_logs,
    like_log,
    unlike_log,
    visible_logs,
)
from common.pagination import DefaultCursorPagination

FEED_SCOPES = ("explore", "following")


def _get_visible_log(request, pk) -> ClimbLog:
    """본인 것이거나 공개된 기록만. 남의 비공개 기록은 존재 자체를 숨긴다(404)."""
    return generics.get_object_or_404(visible_logs(request.user), pk=pk)


@extend_schema(
    tags=["climbs"],
    parameters=[
        OpenApiParameter("gym", int, description="암장 id 필터"),
        OpenApiParameter("is_success", bool, description="완등 여부 필터"),
    ],
)
class ClimbLogListCreateView(generics.ListCreateAPIView):
    """내 등반 기록 목록(커서) + 작성."""

    queryset = ClimbLog.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    filterset_fields = ("gym", "is_success")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ClimbLogWriteSerializer
        return ClimbLogSerializer

    def get_queryset(self):
        return annotated_logs(self.request.user).filter(user=self.request.user)

    @extend_schema(request=ClimbLogWriteSerializer, responses={201: ClimbLogSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(user=request.user)
        data = ClimbLogSerializer(annotated_logs(request.user).get(pk=log.pk)).data
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["climbs"])
class ClimbLogDetailView(generics.RetrieveUpdateDestroyAPIView):
    """기록 상세 — 조회는 본인 또는 공개 기록, 수정/삭제는 작성자만."""

    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ClimbLogWriteSerializer
        return ClimbLogSerializer

    def get_queryset(self):
        return visible_logs(self.request.user)

    def get_object(self):
        log = super().get_object()
        is_write = self.request.method in ("PATCH", "DELETE")
        if is_write and log.user_id != self.request.user.id:
            raise PermissionDenied("본인의 기록만 수정·삭제할 수 있습니다.")
        return log

    @extend_schema(request=ClimbLogWriteSerializer, responses=ClimbLogSerializer)
    def partial_update(self, request, *args, **kwargs):
        log = self.get_object()
        serializer = self.get_serializer(log, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = ClimbLogSerializer(annotated_logs(request.user).get(pk=log.pk)).data
        return Response(data)


@extend_schema(tags=["climbs"], request=None, responses={204: None})
class ClimbLogLikeView(APIView):
    """좋아요 (POST, 멱등) / 취소 (DELETE, 멱등)."""

    def post(self, request, pk):
        like_log(_get_visible_log(request, pk), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, pk):
        unlike_log(_get_visible_log(request, pk), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentCursorPagination(DefaultCursorPagination):
    """댓글은 대화 흐름대로 오래된 것부터."""

    ordering = "created_at"


@extend_schema(tags=["climbs"])
class ClimbLogCommentListCreateView(generics.ListCreateAPIView):
    """기록 댓글 목록(커서, 오래된 순) + 작성. 1단계 답글은 parent 로."""

    queryset = ClimbLogComment.objects.none()  # 스키마 생성용
    serializer_class = ClimbLogCommentSerializer
    pagination_class = CommentCursorPagination

    def get_log(self) -> ClimbLog:
        if not hasattr(self, "_log"):
            self._log = _get_visible_log(self.request, self.kwargs["pk"])
        return self._log

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["climb_log"] = self.get_log()
        return context

    def get_queryset(self):
        return ClimbLogComment.objects.filter(climb_log=self.get_log()).select_related(
            "user__profile"
        )

    def perform_create(self, serializer):
        serializer.instance = create_comment(
            self.get_log(),
            self.request.user,
            serializer.validated_data["content"],
            serializer.validated_data.get("parent"),
        )


@extend_schema(tags=["climbs"])
class ClimbLogCommentDeleteView(generics.DestroyAPIView):
    """댓글 삭제 — 작성자만, soft delete."""

    serializer_class = ClimbLogCommentSerializer

    def get_object(self):
        log = _get_visible_log(self.request, self.kwargs["pk"])
        comment = generics.get_object_or_404(
            ClimbLogComment, pk=self.kwargs["comment_id"], climb_log=log
        )
        if comment.user_id != self.request.user.id:
            raise PermissionDenied("본인의 댓글만 삭제할 수 있습니다.")
        return comment


@extend_schema(
    tags=["climbs"],
    parameters=[
        OpenApiParameter(
            "scope",
            str,
            enum=FEED_SCOPES,
            description="explore(기본, 전체 공개 기록) | following(팔로우한 회원)",
        )
    ],
)
class FeedView(generics.ListAPIView):
    """피드 — 공개 기록을 최신순 커서 페이지네이션. 로그인 필수."""

    queryset = ClimbLog.objects.none()  # 스키마 생성용
    serializer_class = ClimbLogSerializer

    def get_queryset(self):
        scope = self.request.query_params.get("scope", "explore")
        if scope not in FEED_SCOPES:
            raise ValidationError({"scope": "scope 는 explore 또는 following 입니다."})
        return feed_logs(self.request.user, scope)


@extend_schema(tags=["climbs"])
class UserLogListView(generics.ListAPIView):
    """회원의 기록 목록 (공개 프로필용). 본인이면 전부, 타인이면 is_shared 만."""

    queryset = ClimbLog.objects.none()  # 스키마 생성용
    serializer_class = ClimbLogSerializer

    def get_queryset(self):
        owner = generics.get_object_or_404(
            get_user_model().objects, pk=self.kwargs["user_id"]
        )
        return visible_logs(self.request.user).filter(user=owner)
