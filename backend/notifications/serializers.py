from rest_framework import serializers

from accounts.models import User
from notifications.models import Notification, NotificationSetting, PushSubscription


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


class NotificationSettingSerializer(serializers.ModelSerializer):
    """푸시/이메일 팬아웃 스위치. PATCH 는 partial — 둘 중 하나만 보내도 된다."""

    class Meta:
        model = NotificationSetting
        fields = ("push_enabled", "email_enabled")


class PushPublicKeySerializer(serializers.Serializer):
    public_key = serializers.CharField(
        help_text="VAPID 공개키 (base64url). pushManager.subscribe 의 applicationServerKey"
    )


class PushKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField(max_length=255)
    auth = serializers.CharField(max_length=255)


class PushSubscribeSerializer(serializers.Serializer):
    """브라우저 PushSubscription.toJSON() 모양 그대로 (+ 선택 user_agent)."""

    endpoint = serializers.URLField(max_length=500)
    keys = PushKeysSerializer()
    user_agent = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=True
    )

    def validate_endpoint(self, value: str) -> str:
        if not value.lower().startswith("https://"):
            raise serializers.ValidationError("endpoint 는 https URL 이어야 합니다.")
        return value


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ("id", "endpoint", "created_at")
        read_only_fields = fields


class PushUnsubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=500)
