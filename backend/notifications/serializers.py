from rest_framework import serializers

from accounts.models import User
from notifications.models import Notification


class ActorSerializer(serializers.ModelSerializer):
    """알림 행위자 요약. image 는 프로필에서 (select_related("actor__profile") 전제)."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nickname", "image")
        read_only_fields = fields

    def get_image(self, obj) -> str | None:
        profile = getattr(obj, "profile", None)
        return (profile.image or None) if profile else None


class NotificationSerializer(serializers.ModelSerializer):
    """REST 응답과 WebSocket 페이로드가 같은 모양을 쓴다."""

    actor = ActorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "type",
            "actor",
            "target_type",
            "target_id",
            "message",
            "is_read",
            "created_at",
        )
        read_only_fields = fields


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class ReadAllSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
