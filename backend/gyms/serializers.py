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


class GymListSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(source="location.y", read_only=True)
    lng = serializers.FloatField(source="location.x", read_only=True)
    distance_m = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Gym
        fields = ("id", "name", "address", "lat", "lng", "distance_m", "thumbnail")

    def get_distance_m(self, obj):
        distance = getattr(obj, "distance", None)
        return round(distance.m, 1) if distance is not None else None

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
        )


class GymReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = GymReview
        fields = ("id", "user", "rating", "content", "created_at")
        read_only_fields = ("id", "user", "created_at")
