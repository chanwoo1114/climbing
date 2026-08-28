import re

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer
from gyms.models import (
    Gym,
    GymDifficulty,
    GymFacility,
    GymImage,
    GymManager,
    GymPrice,
    GymReview,
)
from gyms.services import is_gym_manager

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class GymDifficultySerializer(serializers.ModelSerializer):
    """읽기(공개 목록) + 관리자 생성/수정 공용. gym 은 뷰가 URL 에서 넣는다."""

    class Meta:
        model = GymDifficulty
        fields = ("id", "name", "color", "order")

    def validate_color(self, value: str) -> str:
        if not HEX_COLOR_RE.match(value):
            raise serializers.ValidationError("색상은 #rrggbb 형식이어야 합니다.")
        return value.lower()


class GymImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymImage
        fields = ("id", "image", "order")


class GymPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymPrice
        fields = ("id", "name", "price", "note")


class GymFacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = GymFacility
        fields = ("id", "name")


class GymPointSerializer(serializers.ModelSerializer):
    """지도 마커/클러스터용 최소 필드. 전국을 한 번에 내려준다."""

    lat = serializers.FloatField(source="location.y", read_only=True)
    lng = serializers.FloatField(source="location.x", read_only=True)

    class Meta:
        model = Gym
        fields = ("id", "name", "lat", "lng")


class GymListSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(source="location.y", read_only=True)
    lng = serializers.FloatField(source="location.x", read_only=True)
    distance_m = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Gym
        fields = ("id", "name", "address", "lat", "lng", "distance_m", "thumbnail")

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_distance_m(self, obj):
        distance = getattr(obj, "distance", None)
        return round(distance.m, 1) if distance is not None else None

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_thumbnail(self, obj):
        first = obj.images.first()
        return first.image if first else None


class GymDetailSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(source="location.y", read_only=True)
    lng = serializers.FloatField(source="location.x", read_only=True)
    images = GymImageSerializer(many=True, read_only=True)
    prices = GymPriceSerializer(many=True, read_only=True)
    facilities = GymFacilitySerializer(many=True, read_only=True)
    difficulties = GymDifficultySerializer(many=True, read_only=True)
    # 뷰에서 annotate — 리뷰 헤더(평균·개수)를 페이지 단위가 아닌 전체 기준으로
    review_count = serializers.IntegerField(read_only=True)
    rating_avg = serializers.FloatField(read_only=True, allow_null=True)
    # 요청자가 이 암장의 관리자(또는 운영자)인지 — 프론트가 편집 UI 노출 여부를 정한다
    is_manager = serializers.SerializerMethodField()

    class Meta:
        model = Gym
        fields = (
            "id",
            "name",
            "description",
            "address",
            "lat",
            "lng",
            "phone",
            "website",
            "images",
            "prices",
            "facilities",
            "difficulties",
            "review_count",
            "rating_avg",
            "is_manager",
        )

    def get_is_manager(self, obj) -> bool:
        request = self.context.get("request")
        return is_gym_manager(obj, getattr(request, "user", None))


REVIEW_MAX_LENGTH = 500  # front/src/pages/GymDetail.tsx REVIEW_MAX_LENGTH 와 동일 유지


class GymReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    content = serializers.CharField(
        max_length=REVIEW_MAX_LENGTH,
        error_messages={
            "blank": "리뷰 내용을 입력해 주세요.",
            "max_length": f"리뷰는 {REVIEW_MAX_LENGTH}자 이하여야 합니다.",
        },
    )

    class Meta:
        model = GymReview
        fields = ("id", "user", "rating", "content", "created_at")
        read_only_fields = ("id", "user", "created_at")


# ---------- 암장 관리자 기능 ----------


class GymUpdateSerializer(serializers.ModelSerializer):
    """관리자 PATCH — 위치(location)는 API 로 바꾸지 않는다 (crawler/admin 담당)."""

    class Meta:
        model = Gym
        fields = ("name", "description", "address", "phone", "website")
        extra_kwargs = {
            "name": {"required": False},
            "address": {"required": False},
        }


class GymImageCreateSerializer(serializers.ModelSerializer):
    """사진 추가 — image 는 presigned PUT 으로 올린 뒤의 URL. order 생략 시 맨 뒤."""

    order = serializers.IntegerField(required=False, min_value=0)

    class Meta:
        model = GymImage
        fields = ("image", "order")


class GymImageOrderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class GymManagerUserSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nickname", "image")
        read_only_fields = fields

    def get_image(self, obj) -> str | None:
        profile = getattr(obj, "profile", None)
        return (profile.image or None) if profile else None


class GymManagerSerializer(serializers.ModelSerializer):
    user = GymManagerUserSerializer(read_only=True)

    class Meta:
        model = GymManager
        fields = ("id", "user", "note", "created_at")
        read_only_fields = fields


class GymManagerCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    note = serializers.CharField(max_length=100, required=False, allow_blank=True)
