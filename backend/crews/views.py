from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from climbs.models import ClimbLog
from climbs.serializers import ClimbLogSerializer
from common.pagination import DefaultCursorPagination
from community.models import Post
from community.serializers import PostListSerializer
from crews.models import Crew, CrewMember
from climbs.stats import parse_month
from crews.serializers import (
    CrewListSerializer,
    CrewMemberSerializer,
    CrewMemberUpdateSerializer,
    CrewRankSerializer,
    CrewSerializer,
    CrewStatsSerializer,
    CrewWriteSerializer,
)
from crews.services import (
    annotated_crews,
    crew_feed,
    crew_members,
    crew_recruitments,
    delete_crew,
    get_membership,
    join_crew,
    kick_member,
    leave_crew,
    set_member_role,
    set_member_status,
)
from crews.stats import (
    CREW_RANKING_DEFAULT_LIMIT,
    CREW_RANKING_MAX_LIMIT,
    crew_ranking,
    crew_stats,
)


def _get_crew(pk) -> Crew:
    return generics.get_object_or_404(Crew.objects.select_related("chat_room"), pk=pk)


def _crew_detail_data(request, pk) -> dict:
    return CrewSerializer(
        annotated_crews(request.user).get(pk=pk), context={"request": request}
    ).data


def _require_manager(crew: Crew, user, message: str) -> CrewMember:
    """크루장/운영진(활동 중)만. 아니면 403."""
    membership = get_membership(crew, user)
    if membership is None or not membership.is_manager:
        raise PermissionDenied(message)
    return membership


def _require_owner(crew: Crew, user, message: str) -> None:
    if crew.owner_id != user.id:
        raise PermissionDenied(message)


class OldestFirstPagination(DefaultCursorPagination):
    """크루원은 가입 순(오래된 것부터)."""

    ordering = "created_at"


# --- 크루 ---------------------------------------------------------------------


@extend_schema(
    tags=["crews"],
    parameters=[
        OpenApiParameter("gym", int, description="주 활동 암장 id 필터"),
        OpenApiParameter("q", str, description="크루 이름 검색 (부분 일치)"),
    ],
)
class CrewListCreateView(generics.ListCreateAPIView):
    """크루 목록(커서, 최신순) + 생성. 생성 시 단톡방과 크루장 소속이 함께 만들어진다."""

    queryset = Crew.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CrewWriteSerializer
        return CrewListSerializer

    def get_queryset(self):
        queryset = annotated_crews(self.request.user)
        gym = self.request.query_params.get("gym")
        if gym:
            if not gym.isdigit():
                raise ValidationError({"gym": "gym 은 암장 id(정수)여야 합니다."})
            queryset = queryset.filter(home_gym_id=int(gym))
        q = self.request.query_params.get("q", "").strip()
        if q:
            queryset = queryset.filter(name__icontains=q)
        return queryset

    @extend_schema(request=CrewWriteSerializer, responses={201: CrewSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crew = serializer.save()
        return Response(
            _crew_detail_data(request, crew.pk), status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["crews"])
class CrewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """크루 상세. 수정은 크루장/운영진, 삭제는 크루장만 (soft, 단톡방은 유지)."""

    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CrewWriteSerializer
        return CrewSerializer

    def get_queryset(self):
        return annotated_crews(self.request.user)

    def get_object(self):
        crew = super().get_object()
        if self.request.method == "PATCH":
            _require_manager(
                crew, self.request.user, "크루장·운영진만 수정할 수 있습니다."
            )
        elif self.request.method == "DELETE":
            _require_owner(crew, self.request.user, "크루장만 삭제할 수 있습니다.")
        return crew

    @extend_schema(request=CrewWriteSerializer, responses=CrewSerializer)
    def partial_update(self, request, *args, **kwargs):
        crew = self.get_object()
        serializer = self.get_serializer(crew, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_crew_detail_data(request, crew.pk))

    def perform_destroy(self, instance):
        delete_crew(instance)


# --- 가입 / 탈퇴 ---------------------------------------------------------------


@extend_schema(tags=["crews"], request=None, responses={201: CrewMemberSerializer})
class CrewJoinView(APIView):
    """가입 신청 — instant 즉시 활동(+단톡방) / approval 승인 대기. 정원 초과·중복은 400."""

    def post(self, request, pk):
        member = join_crew(_get_crew(pk), request.user)
        member.user = request.user
        return Response(
            CrewMemberSerializer(member).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["crews"], request=None, responses={204: None})
class CrewLeaveView(APIView):
    """탈퇴 (soft) — 크루장은 불가(400). 활동 중이었으면 단톡방에서도 나간다."""

    def delete(self, request, pk):
        leave_crew(_get_crew(pk), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- 크루원 -------------------------------------------------------------------


@extend_schema(
    tags=["crews"],
    parameters=[
        OpenApiParameter(
            "status",
            str,
            enum=CrewMember.Status.values,
            description="active(기본) | pending — 승인 대기는 크루장·운영진만 조회",
        )
    ],
)
class CrewMemberListView(generics.ListAPIView):
    """크루원 목록 (커서, 가입 순)."""

    queryset = CrewMember.objects.none()  # 스키마 생성용
    serializer_class = CrewMemberSerializer
    pagination_class = OldestFirstPagination

    def get_queryset(self):
        crew = _get_crew(self.kwargs["pk"])
        member_status = self.request.query_params.get(
            "status", CrewMember.Status.ACTIVE
        )
        if member_status not in CrewMember.Status.values:
            raise ValidationError({"status": "status 는 active 또는 pending 입니다."})
        if member_status == CrewMember.Status.PENDING:
            _require_manager(
                crew,
                self.request.user,
                "승인 대기 목록은 크루장·운영진만 볼 수 있습니다.",
            )
        return crew_members(crew, member_status)


@extend_schema(tags=["crews"])
class CrewMemberDetailView(APIView):
    """크루원 관리.

    PATCH {status: active|rejected} — 승인 대기 신청 승인/거절 (크루장·운영진)
    PATCH {role: staff|member}     — 역할 변경 (크루장만, 크루장 본인은 불가)
    DELETE                          — 강퇴 (크루장·운영진, 운영진은 크루원만)
    """

    @extend_schema(request=CrewMemberUpdateSerializer, responses=CrewMemberSerializer)
    def patch(self, request, pk, user_id):
        crew = _get_crew(pk)
        _require_manager(
            crew, request.user, "크루장·운영진만 크루원을 관리할 수 있습니다."
        )
        serializer = CrewMemberUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "role" in data:
            _require_owner(crew, request.user, "역할은 크루장만 변경할 수 있습니다.")
            member = set_member_role(crew, user_id, data["role"])
            if member is None:
                raise NotFound("활동 중인 크루원이 아닙니다.")
        else:
            member = set_member_status(crew, user_id, data["status"])
            if member is None:
                raise NotFound("승인 대기 중인 신청을 찾을 수 없습니다.")

        member = CrewMember.all_objects.select_related("user__profile").get(
            pk=member.pk
        )
        return Response(CrewMemberSerializer(member).data)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, pk, user_id):
        crew = _get_crew(pk)
        actor = _require_manager(
            crew, request.user, "크루장·운영진만 내보낼 수 있습니다."
        )
        target = (
            CrewMember.objects.select_related("user")
            .filter(crew=crew, user_id=user_id)
            .first()
        )
        if target is None:
            raise NotFound("크루원을 찾을 수 없습니다.")
        if target.role == CrewMember.Role.OWNER:
            raise PermissionDenied("크루장은 내보낼 수 없습니다.")
        if actor.role == CrewMember.Role.STAFF and target.role == CrewMember.Role.STAFF:
            raise PermissionDenied("운영진은 크루장만 내보낼 수 있습니다.")
        kick_member(crew, target)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- 피드 / 모집 -----------------------------------------------------------------


@extend_schema(tags=["crews"])
def _require_feed_access(crew: Crew, user) -> None:
    """크루 피드/통계 — 크루원(활동 중)만, 또는 is_feed_public 이면 누구나."""
    if crew.is_feed_public:
        return
    membership = get_membership(crew, user)
    if membership is None or membership.status != CrewMember.Status.ACTIVE:
        raise PermissionDenied("크루원만 볼 수 있는 피드입니다.")


class CrewFeedView(generics.ListAPIView):
    """크루 피드 — 활동 중인 크루원들의 공개 기록. 크루원만, 또는 is_feed_public 이면 누구나."""

    queryset = ClimbLog.objects.none()  # 스키마 생성용
    serializer_class = ClimbLogSerializer

    def get_queryset(self):
        crew = _get_crew(self.kwargs["pk"])
        _require_feed_access(crew, self.request.user)
        return crew_feed(crew, self.request.user)


MONTH_PARAMETER = OpenApiParameter(
    "month", str, description="YYYY-MM (기본 이번 달, Asia/Seoul)"
)


@extend_schema(
    tags=["crews"], parameters=[MONTH_PARAMETER], responses=CrewStatsSerializer
)
class CrewStatsView(APIView):
    """크루 월간 통계 — 완등 수/성공률/암장 수 + 크루원 활동 랭킹. 권한은 크루 피드와 동일."""

    def get(self, request, pk):
        crew = _get_crew(pk)
        _require_feed_access(crew, request.user)
        return Response(
            crew_stats(crew, parse_month(request.query_params.get("month")))
        )


@extend_schema(
    tags=["crews"],
    parameters=[
        MONTH_PARAMETER,
        OpenApiParameter(
            "limit",
            int,
            description=(
                f"상위 몇 개 (기본 {CREW_RANKING_DEFAULT_LIMIT}, "
                f"최대 {CREW_RANKING_MAX_LIMIT})"
            ),
        ),
    ],
    responses=CrewRankSerializer(many=True),
)
class CrewRankingView(APIView):
    """전체 크루 랭킹 — 그 달 활동 중 크루원들의 공개 완등 수 순. 페이지네이션 없음."""

    def get(self, request):
        first_day = parse_month(request.query_params.get("month"))
        raw_limit = request.query_params.get("limit")
        try:
            limit = int(raw_limit) if raw_limit else CREW_RANKING_DEFAULT_LIMIT
        except ValueError:
            raise ValidationError({"limit": ["limit 은 정수여야 합니다."]})
        if not 1 <= limit <= CREW_RANKING_MAX_LIMIT:
            raise ValidationError(
                {"limit": [f"limit 은 1~{CREW_RANKING_MAX_LIMIT} 사이여야 합니다."]}
            )
        return Response(crew_ranking(first_day, limit))


@extend_schema(tags=["crews"])
class CrewRecruitmentListView(generics.ListAPIView):
    """크루 주최 모집글 목록 (커서, 최신순)."""

    queryset = Post.objects.none()  # 스키마 생성용
    serializer_class = PostListSerializer

    def get_queryset(self):
        return crew_recruitments(_get_crew(self.kwargs["pk"]), self.request.user)
