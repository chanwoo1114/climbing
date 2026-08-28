from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from climbs.beta_services import (
    annotated_betas,
    beta_sectors,
    gym_betas,
    increment_view_count,
)
from climbs.models import ClimbBeta, ClimbLog, ClimbLogComment
from climbs.serializers import (
    BetaSectorSerializer,
    ClimbBetaSerializer,
    ClimbBetaWriteSerializer,
    ClimbLogCommentSerializer,
    ClimbLogSerializer,
    ClimbLogWriteSerializer,
    UserStatsSerializer,
)
from climbs.services import (
    annotated_logs,
    create_comment,
    feed_logs,
    like_log,
    unlike_log,
    visible_logs,
)
from climbs.stats import user_stats
from common.pagination import DefaultCursorPagination
from gyms.models import Gym

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


@extend_schema(tags=["climbs"], responses=UserStatsSerializer)
class UserStatsView(APIView):
    """회원 통계 (프로필용) — 성공률·난이도 분포·월별 추이·자주 간 암장.

    본인이면 전체 기록, 타인이면 공개(is_shared) 기록만 집계한다. 탈퇴 회원은 404.
    """

    def get(self, request, user_id):
        owner = generics.get_object_or_404(get_user_model().objects, pk=user_id)
        return Response(user_stats(owner, request.user))


# ---- 베타 영상 (ClimbBeta) ---------------------------------------------------------


def _get_gym(gym_id) -> Gym:
    return generics.get_object_or_404(Gym, pk=gym_id)


@extend_schema(
    tags=["betas"],
    parameters=[
        OpenApiParameter("sector", str, description="섹터 이름 (대소문자 무시 일치)"),
        OpenApiParameter("difficulty", int, description="난이도 id 필터"),
        OpenApiParameter("q", str, description="제목 검색 (부분 일치)"),
    ],
)
class GymBetaListCreateView(generics.ListCreateAPIView):
    """암장 베타 영상 목록(커서, 최신순) — 조회는 공개, 올리기는 로그인 필요.

    영상은 먼저 `POST /uploads/presigned-url/` (kind=beta_video / beta_thumbnail) 로
    직접 업로드한 뒤 그 file_url 을 video_url / thumbnail_url 로 보낸다.
    """

    queryset = ClimbBeta.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ClimbBetaWriteSerializer
        return ClimbBetaSerializer

    def get_gym(self) -> Gym:
        if not hasattr(self, "_gym"):
            self._gym = _get_gym(self.kwargs["gym_id"])
        return self._gym

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["gym"] = self.get_gym()
        return context

    def get_queryset(self):
        params = self.request.query_params
        difficulty_id = params.get("difficulty")
        if difficulty_id is not None and not difficulty_id.isdigit():
            raise ValidationError({"difficulty": "difficulty 는 정수 id 입니다."})
        return gym_betas(
            self.get_gym(),
            sector=params.get("sector"),
            difficulty_id=int(difficulty_id) if difficulty_id else None,
            q=params.get("q"),
        )

    @extend_schema(
        request=ClimbBetaWriteSerializer, responses={201: ClimbBetaSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        beta = serializer.save(user=request.user, gym=self.get_gym())
        data = ClimbBetaSerializer(
            annotated_betas().get(pk=beta.pk), context=self.get_serializer_context()
        ).data
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["betas"], responses=BetaSectorSerializer(many=True))
class GymBetaSectorListView(APIView):
    """암장의 섹터 목록 + 섹터별 베타 개수 (개수 내림차순 → 이름순). 페이지네이션 없음."""

    permission_classes = [AllowAny]

    def get(self, request, gym_id):
        return Response(beta_sectors(_get_gym(gym_id)))


@extend_schema(tags=["betas"])
class ClimbBetaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """베타 상세(공개, 조회수 +1) / 수정·삭제(올린 사람만, soft delete).

    수정 가능: title, sector, difficulty, description, thumbnail_url, climb_log.
    video_url 은 생성 후 변경 불가 — 보내면 400.
    """

    http_method_names = ["get", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ClimbBetaWriteSerializer
        return ClimbBetaSerializer

    def get_queryset(self):
        return annotated_betas()

    def get_object(self):
        beta = super().get_object()
        is_write = self.request.method in ("PATCH", "DELETE")
        if is_write and beta.user_id != self.request.user.id:
            raise PermissionDenied("본인이 올린 베타만 수정·삭제할 수 있습니다.")
        return beta

    def retrieve(self, request, *args, **kwargs):
        beta = self.get_object()
        increment_view_count(beta)
        return Response(self.get_serializer(beta).data)

    @extend_schema(request=ClimbBetaWriteSerializer, responses=ClimbBetaSerializer)
    def partial_update(self, request, *args, **kwargs):
        beta = self.get_object()
        context = {**self.get_serializer_context(), "gym": beta.gym}
        serializer = ClimbBetaWriteSerializer(
            beta, data=request.data, partial=True, context=context
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = ClimbBetaSerializer(
            annotated_betas().get(pk=beta.pk), context=context
        ).data
        return Response(data)
