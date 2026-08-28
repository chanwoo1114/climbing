from django.contrib.gis.db.models.functions import Distance
from django.db.models import Avg, Count, Q
from django.contrib.gis.geos import Point, Polygon
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, mixins, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import (
    SAFE_METHODS,
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from gyms.models import Gym, GymDifficulty, GymImage, GymManager, GymReview
from gyms.serializers import (
    GymDetailSerializer,
    GymDifficultySerializer,
    GymFacilitySerializer,
    GymImageCreateSerializer,
    GymImageOrderSerializer,
    GymImageSerializer,
    GymListSerializer,
    GymManagerCreateSerializer,
    GymManagerSerializer,
    GymPointSerializer,
    GymPriceSerializer,
    GymReviewSerializer,
    GymUpdateSerializer,
)
from gyms.services import (
    add_image,
    add_manager,
    create_difficulty,
    delete_difficulty,
    gym_managers,
    is_gym_manager,
    managed_gyms,
    remove_manager,
    reorder_images,
    replace_facilities,
    replace_prices,
    update_difficulty,
    update_gym,
)

MAX_MAP_RESULTS = 100  # 지도 핀 용도라 페이지네이션 대신 상한
MANAGER_ONLY_MESSAGE = "암장 관리자만 할 수 있습니다."


def _parse_bbox(raw: str) -> Polygon:
    try:
        min_lng, min_lat, max_lng, max_lat = (float(v) for v in raw.split(","))
    except ValueError:
        raise ValidationError(
            {"bbox": "bbox=minLng,minLat,maxLng,maxLat 형식이어야 합니다."}
        )
    return Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))


def _parse_point(lat: str, lng: str) -> Point:
    try:
        return Point(float(lng), float(lat), srid=4326)
    except (TypeError, ValueError):
        raise ValidationError({"lat": "lat/lng는 숫자여야 합니다."})


def _get_gym(pk) -> Gym:
    return generics.get_object_or_404(Gym, pk=pk)


def _require_manager(gym: Gym, user) -> None:
    """암장 관리자(또는 운영자)만. 암장은 공개 자원이라 권한 실패는 404 가 아닌 403."""
    if not is_gym_manager(gym, user):
        raise PermissionDenied(MANAGER_ONLY_MESSAGE)


class GymManagerRequiredMixin:
    """URL 의 gym_id 암장을 self.gym 에 싣고, 관리자/운영자가 아니면 403 (미로그인 401)."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.gym = _get_gym(kwargs["gym_id"])
        _require_manager(self.gym, request.user)


@extend_schema(
    tags=["gyms"],
    parameters=[
        OpenApiParameter(
            "bbox", str, description="뷰포트: minLng,minLat,maxLng,maxLat"
        ),
        OpenApiParameter("lat", float, description="거리순 정렬 기준 위도"),
        OpenApiParameter("lng", float, description="거리순 정렬 기준 경도"),
        OpenApiParameter("radius", float, description="반경(m) — lat/lng와 함께 사용"),
    ],
)
class GymListView(generics.ListAPIView):
    """암장 목록. 지도 뷰포트(bbox) 필터 + 거리순 정렬. 공개."""

    serializer_class = GymListSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # 거리순 정렬과 커서 페이지네이션이 충돌 — 상한으로 대체

    def get_queryset(self):
        params = self.request.query_params
        queryset = Gym.objects.prefetch_related("images")

        if bbox := params.get("bbox"):
            queryset = queryset.filter(location__intersects=_parse_bbox(bbox))

        lat, lng = params.get("lat"), params.get("lng")
        if lat and lng:
            point = _parse_point(lat, lng)
            if radius := params.get("radius"):
                try:
                    queryset = queryset.filter(location__dwithin=(point, float(radius)))
                except ValueError:
                    raise ValidationError(
                        {"radius": "radius는 미터 단위 숫자여야 합니다."}
                    )
            queryset = queryset.annotate(distance=Distance("location", point)).order_by(
                "distance"
            )
        else:
            queryset = queryset.order_by("-created_at")

        return queryset[:MAX_MAP_RESULTS]


@extend_schema(tags=["gyms"])
class GymPointListView(generics.ListAPIView):
    """지도 클러스터용 전국 암장 좌표. 목록 API 의 100건 상한과 달리 전부 내려준다.

    축소된 지도에서 bbox 목록만으로 마커를 찍으면 일부만 보여 "여긴 암장이 없네"로
    오해한다. 클라이언트가 이걸 한 번 받아 캐시하고 MapLibre 가 클러스터링한다.
    """

    serializer_class = GymPointSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = Gym.objects.only("id", "name", "location").order_by("id")


@extend_schema(tags=["gyms"])
class GymManagedListView(generics.ListAPIView):
    """내가 관리하는 암장 목록. 운영자(is_staff)도 명시적으로 지정된 암장만."""

    serializer_class = GymListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = (
        None  # 한 사람이 관리하는 암장은 소수 — 목록 API 와 같은 평면 배열
    )
    queryset = Gym.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset

    def get_queryset(self):
        return managed_gyms(self.request.user)


@extend_schema_view(
    get=extend_schema(tags=["gyms"]),
    patch=extend_schema(
        tags=["gyms"],
        request=GymUpdateSerializer,
        responses=GymDetailSerializer,
        description="암장 정보 수정 — 관리자/운영자만. 위치(lat/lng)는 바꿀 수 없다.",
    ),
)
class GymDetailView(generics.RetrieveUpdateAPIView):
    """암장 상세 (이미지/가격표/편의시설/난이도 포함). 조회는 공개, 수정은 관리자."""

    http_method_names = ["get", "patch", "head", "options"]
    queryset = Gym.objects.prefetch_related(
        "images", "prices", "facilities", "difficulties"
    ).annotate(
        # 삭제된 리뷰는 집계에서 뺀다 (related manager 는 all_objects 기준으로 조인됨)
        review_count=Count("reviews", filter=Q(reviews__is_deleted=False)),
        rating_avg=Avg("reviews__rating", filter=Q(reviews__is_deleted=False)),
    )
    serializer_class = GymDetailSerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def patch(self, request, *args, **kwargs):
        gym = self.get_object()
        _require_manager(gym, request.user)
        serializer = GymUpdateSerializer(gym, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        update_gym(gym, **serializer.validated_data)
        # 어노테이션(리뷰 집계)까지 포함한 최신 상세를 돌려준다
        return Response(self.get_serializer(self.get_object()).data)


@extend_schema_view(
    get=extend_schema(tags=["gyms"]),
    post=extend_schema(
        tags=["gyms"], description="난이도 추가 — 관리자/운영자만. 같은 이름 중복 불가."
    ),
)
class GymDifficultyListView(generics.ListCreateAPIView):
    """암장 난이도 목록(공개) + 추가(관리자)."""

    queryset = GymDifficulty.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    serializer_class = GymDifficultySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return GymDifficulty.objects.filter(gym_id=self.kwargs["gym_id"])

    def perform_create(self, serializer):
        gym = _get_gym(self.kwargs["gym_id"])
        _require_manager(gym, self.request.user)
        serializer.instance = create_difficulty(gym, **serializer.validated_data)


@extend_schema(tags=["gyms"])
class GymDifficultyDetailView(
    GymManagerRequiredMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    generics.GenericAPIView,
):
    """난이도 수정/삭제 — 관리자/운영자만. 삭제는 soft delete (기존 기록의 FK 는 유지)."""

    queryset = GymDifficulty.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    serializer_class = GymDifficultySerializer
    lookup_url_kwarg = "difficulty_id"

    def get_queryset(self):
        return GymDifficulty.objects.filter(gym_id=self.kwargs["gym_id"])

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def perform_update(self, serializer):
        update_difficulty(serializer.instance, **serializer.validated_data)

    def perform_destroy(self, instance):
        delete_difficulty(instance)


@extend_schema(
    tags=["gyms"],
    request=GymImageCreateSerializer,
    responses={201: GymImageSerializer},
    description="사진 추가 — 관리자/운영자만. image 는 presigned PUT 으로 올린 URL.",
)
class GymImageCreateView(GymManagerRequiredMixin, generics.CreateAPIView):
    serializer_class = GymImageCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = add_image(self.gym, **serializer.validated_data)
        return Response(GymImageSerializer(image).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["gyms"], description="사진 삭제 — 관리자/운영자만.")
class GymImageDeleteView(GymManagerRequiredMixin, generics.DestroyAPIView):
    queryset = GymImage.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    serializer_class = GymImageSerializer
    lookup_url_kwarg = "image_id"

    def get_queryset(self):
        return GymImage.objects.filter(gym_id=self.kwargs["gym_id"])


@extend_schema(
    tags=["gyms"],
    request=GymImageOrderSerializer,
    responses=GymImageSerializer(many=True),
    description="사진 순서 변경 — ids 순서대로 order 재부여. 관리자/운영자만.",
)
class GymImageOrderView(GymManagerRequiredMixin, APIView):
    def put(self, request, gym_id):
        serializer = GymImageOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        images = reorder_images(self.gym, serializer.validated_data["ids"])
        return Response(GymImageSerializer(images, many=True).data)


@extend_schema(
    tags=["gyms"],
    request=GymPriceSerializer(many=True),
    responses=GymPriceSerializer(many=True),
    description="가격표 전체 교체 — 빈 배열이면 모두 삭제. 관리자/운영자만.",
)
class GymPriceReplaceView(GymManagerRequiredMixin, APIView):
    def put(self, request, gym_id):
        serializer = GymPriceSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        prices = replace_prices(self.gym, serializer.validated_data)
        return Response(GymPriceSerializer(prices, many=True).data)


@extend_schema(
    tags=["gyms"],
    request=GymFacilitySerializer(many=True),
    responses=GymFacilitySerializer(many=True),
    description="편의시설 전체 교체 — 빈 배열이면 모두 삭제. 관리자/운영자만.",
)
class GymFacilityReplaceView(GymManagerRequiredMixin, APIView):
    def put(self, request, gym_id):
        serializer = GymFacilitySerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        facilities = replace_facilities(self.gym, serializer.validated_data)
        return Response(GymFacilitySerializer(facilities, many=True).data)


@extend_schema_view(
    get=extend_schema(tags=["gyms"], description="관리자 목록 — 관리자/운영자만."),
    post=extend_schema(
        tags=["gyms"],
        request=GymManagerCreateSerializer,
        responses={201: GymManagerSerializer, 200: GymManagerSerializer},
        description="관리자 추가 — 이미 관리자면 200 으로 기존 행을 돌려준다 (멱등).",
    ),
)
class GymManagerListCreateView(GymManagerRequiredMixin, generics.ListCreateAPIView):
    serializer_class = GymManagerSerializer
    pagination_class = None
    queryset = GymManager.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset

    def get_queryset(self):
        return gym_managers(self.gym)

    def create(self, request, *args, **kwargs):
        serializer = GymManagerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row, created = add_manager(
            self.gym,
            serializer.validated_data["user_id"],
            assigned_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(
            GymManagerSerializer(row).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@extend_schema(
    tags=["gyms"],
    responses={204: None},
    description=(
        "관리자 해제 — 관리자/운영자만. 본인 해제 가능. "
        "마지막 관리자는 운영자가 아니면 409 last_manager."
    ),
)
class GymManagerDeleteView(GymManagerRequiredMixin, APIView):
    def delete(self, request, gym_id, user_id):
        remove_manager(self.gym, user_id, force=request.user.is_staff)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["gyms"])
class GymReviewListCreateView(generics.ListCreateAPIView):
    """암장 리뷰 — 조회는 공개, 작성은 로그인 필요."""

    queryset = GymReview.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    serializer_class = GymReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return GymReview.objects.filter(gym_id=self.kwargs["gym_id"]).select_related(
            "user"
        )

    def perform_create(self, serializer):
        generics.get_object_or_404(Gym, pk=self.kwargs["gym_id"])
        serializer.save(user=self.request.user, gym_id=self.kwargs["gym_id"])
