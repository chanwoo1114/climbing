from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from climbs.models import ClimbLog, ClimbLogComment
from gyms.models import Gym, GymDifficulty

MEMO_MAX_LENGTH = 1000
COMMENT_MAX_LENGTH = 500


class LogUserSerializer(serializers.ModelSerializer):
    """피드 카드용 작성자 요약. image 는 프로필에서 가져온다 (select_related 전제)."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nickname", "image")
        read_only_fields = fields

    def get_image(self, obj) -> str | None:
        try:
            return obj.profile.image or None
        except User.profile.RelatedObjectDoesNotExist:
            return None


class LogGymSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gym
        fields = ("id", "name")
        read_only_fields = fields


class LogDifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = GymDifficulty
        fields = ("id", "name", "color")
        read_only_fields = fields


class ClimbLogSerializer(serializers.ModelSerializer):
    """읽기 전용 — 목록/피드/상세 공용. 카운트·is_liked 는 services.annotated_logs 주석값."""

    user = LogUserSerializer(read_only=True)
    gym = LogGymSerializer(read_only=True)
    difficulty = LogDifficultySerializer(read_only=True, allow_null=True)
    like_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)

    class Meta:
        model = ClimbLog
        fields = (
            "id",
            "user",
            "gym",
            "difficulty",
            "is_success",
            "attempts",
            "memo",
            "video_url",
            "climbed_at",
            "is_shared",
            "like_count",
            "comment_count",
            "is_liked",
            "created_at",
        )
        read_only_fields = fields


class ClimbLogWriteSerializer(serializers.ModelSerializer):
    """생성/수정 입력. 응답은 ClimbLogSerializer 로 다시 내려준다."""

    gym = serializers.PrimaryKeyRelatedField(queryset=Gym.objects.all())
    difficulty = serializers.PrimaryKeyRelatedField(
        queryset=GymDifficulty.objects.all(), allow_null=True, required=False
    )
    attempts = serializers.IntegerField(
        min_value=1,
        required=False,
        error_messages={"min_value": "시도 횟수는 1 이상이어야 합니다."},
    )
    memo = serializers.CharField(
        max_length=MEMO_MAX_LENGTH,
        allow_blank=True,
        required=False,
        error_messages={"max_length": f"메모는 {MEMO_MAX_LENGTH}자 이하여야 합니다."},
    )

    class Meta:
        model = ClimbLog
        fields = (
            "gym",
            "difficulty",
            "is_success",
            "attempts",
            "memo",
            "video_url",
            "climbed_at",
            "is_shared",
        )

    def validate_climbed_at(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("미래 날짜는 기록할 수 없습니다.")
        return value

    def validate(self, attrs):
        # partial update 에서 gym 만 바꾸거나 difficulty 만 바꿔도 짝이 맞아야 한다.
        gym = attrs.get("gym", getattr(self.instance, "gym", None))
        difficulty = attrs.get("difficulty", getattr(self.instance, "difficulty", None))
        if difficulty is not None and gym is not None and difficulty.gym_id != gym.id:
            raise serializers.ValidationError(
                {"difficulty": "선택한 암장의 난이도가 아닙니다."}
            )
        return attrs


class ClimbLogCommentSerializer(serializers.ModelSerializer):
    user = LogUserSerializer(read_only=True)
    content = serializers.CharField(
        max_length=COMMENT_MAX_LENGTH,
        error_messages={
            "blank": "댓글 내용을 입력해 주세요.",
            "max_length": f"댓글은 {COMMENT_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    parent = serializers.PrimaryKeyRelatedField(
        queryset=ClimbLogComment.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = ClimbLogComment
        fields = ("id", "user", "content", "parent", "created_at")
        read_only_fields = ("id", "user", "created_at")

    def validate_parent(self, parent):
        if parent is None:
            return parent
        log = self.context["climb_log"]
        if parent.climb_log_id != log.id:
            raise serializers.ValidationError(
                "같은 기록의 댓글에만 답글을 달 수 있습니다."
            )
        if parent.parent_id is not None:
            raise serializers.ValidationError("답글에는 다시 답글을 달 수 없습니다.")
        return parent
