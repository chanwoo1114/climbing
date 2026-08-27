from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.serializers import UserSerializer
from gyms.models import Gym, GymDifficulty, GymFacility, GymImage, GymPrice, GymReview


class GymDifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = GymDifficulty
        fields = ("id", "name", "color", "order")


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
        )


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
