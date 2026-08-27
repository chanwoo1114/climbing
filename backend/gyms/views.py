from django.contrib.gis.db.models.functions import Distance
from django.db.models import Avg, Count, Q
from django.contrib.gis.geos import Point, Polygon
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly

from gyms.models import Gym, GymDifficulty, GymReview
from gyms.serializers import (
    GymDetailSerializer,
    GymDifficultySerializer,
    GymListSerializer,
    GymPointSerializer,
    GymReviewSerializer,
)

MAX_MAP_RESULTS = 100  # 지도 핀 용도라 페이지네이션 대신 상한


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
class GymDetailView(generics.RetrieveAPIView):
    """암장 상세 (이미지/가격표/편의시설/난이도 포함). 공개."""

    queryset = Gym.objects.prefetch_related(
        "images", "prices", "facilities", "difficulties"
    ).annotate(
        # 삭제된 리뷰는 집계에서 뺀다 (related manager 는 all_objects 기준으로 조인됨)
        review_count=Count("reviews", filter=Q(reviews__is_deleted=False)),
        rating_avg=Avg("reviews__rating", filter=Q(reviews__is_deleted=False)),
    )
    serializer_class = GymDetailSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=["gyms"])
class GymDifficultyListView(generics.ListAPIView):
    """암장 난이도 목록. 공개."""

    queryset = GymDifficulty.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    serializer_class = GymDifficultySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return GymDifficulty.objects.filter(gym_id=self.kwargs["gym_id"])


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
