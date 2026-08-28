from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from climbs.models import (
    BETA_DESCRIPTION_MAX_LENGTH,
    BETA_SECTOR_MAX_LENGTH,
    ClimbBeta,
    ClimbLog,
    ClimbLogComment,
)
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


# ---- 통계 (climbs/stats.py 결과 — 읽기 전용 스키마) -----------------------------


class StatsGymSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class StatsDifficultySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    order = serializers.IntegerField()


class MonthCountSerializer(serializers.Serializer):
    month = serializers.CharField(help_text="YYYY-MM")
    total_count = serializers.IntegerField()
    success_count = serializers.IntegerField()


class DifficultyCountSerializer(serializers.Serializer):
    gym = StatsGymSerializer()
    difficulty = StatsDifficultySerializer()
    total_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    success_rate = serializers.FloatField(help_text="0~100")


class GymCountSerializer(serializers.Serializer):
    gym = StatsGymSerializer()
    total_count = serializers.IntegerField()
    success_count = serializers.IntegerField()


class UserStatsSerializer(serializers.Serializer):
    """회원 통계 응답. 본인이면 전체 기록, 타인이면 공개 기록만 집계한 값이다."""

    total_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    success_rate = serializers.FloatField(help_text="0~100")
    gym_count = serializers.IntegerField()
    avg_attempts = serializers.FloatField(allow_null=True)
    this_month = MonthCountSerializer()
    by_month = MonthCountSerializer(many=True, help_text="최근 12개월, 오래된 달부터")
    by_difficulty = DifficultyCountSerializer(many=True)
    top_gyms = GymCountSerializer(many=True)


# ---- 베타 영상 (ClimbBeta) ---------------------------------------------------------


class BetaDifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = GymDifficulty
        fields = ("id", "name", "color", "order")
        read_only_fields = fields


class ClimbBetaSerializer(serializers.ModelSerializer):
    """읽기 전용 — 목록/상세 공용. 공개 API 라 익명이면 is_mine=False."""

    user = LogUserSerializer(read_only=True)
    gym = LogGymSerializer(read_only=True)
    difficulty = BetaDifficultySerializer(read_only=True, allow_null=True)
    climb_log_id = serializers.IntegerField(read_only=True, allow_null=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = ClimbBeta
        fields = (
            "id",
            "user",
            "gym",
            "difficulty",
            "sector",
            "title",
            "description",
            "video_url",
            "thumbnail_url",
            "climb_log_id",
            "view_count",
            "created_at",
            "is_mine",
        )
        read_only_fields = fields

    def get_is_mine(self, obj) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.user_id == user.id)


class ClimbBetaWriteSerializer(serializers.ModelSerializer):
    """생성/수정 입력. context["gym"] 필수. 응답은 ClimbBetaSerializer 로 내려준다.

    video_url 은 생성 시에만 받는다 — 업로드 후 영상을 바꾸려면 새 베타로 올린다.
    """

    title = serializers.CharField(
        max_length=100,
        error_messages={
            "blank": "제목을 입력해 주세요.",
            "max_length": "제목은 100자 이하여야 합니다.",
        },
    )
    sector = serializers.CharField(
        max_length=BETA_SECTOR_MAX_LENGTH,
        allow_blank=True,
        required=False,
        error_messages={
            "max_length": f"섹터 이름은 {BETA_SECTOR_MAX_LENGTH}자 이하여야 합니다."
        },
    )
    difficulty = serializers.PrimaryKeyRelatedField(
        queryset=GymDifficulty.objects.all(), allow_null=True, required=False
    )
    description = serializers.CharField(
        max_length=BETA_DESCRIPTION_MAX_LENGTH,
        allow_blank=True,
        required=False,
        error_messages={
            "max_length": f"설명은 {BETA_DESCRIPTION_MAX_LENGTH}자 이하여야 합니다."
        },
    )
    thumbnail_url = serializers.URLField(allow_blank=True, required=False)
    climb_log = serializers.PrimaryKeyRelatedField(
        queryset=ClimbLog.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = ClimbBeta
        fields = (
            "title",
            "sector",
            "difficulty",
            "description",
            "video_url",
            "thumbnail_url",
            "climb_log",
        )

    def validate_sector(self, value):
        return value.strip()

    def validate(self, attrs):
        gym = self.context["gym"]
        request = self.context["request"]
        if self.instance is not None and "video_url" in self.initial_data:
            raise serializers.ValidationError(
                {"video_url": "영상은 수정할 수 없습니다. 새 베타로 올려 주세요."}
            )

        difficulty = attrs.get("difficulty", getattr(self.instance, "difficulty", None))
        if difficulty is not None and difficulty.gym_id != gym.id:
            raise serializers.ValidationError(
                {"difficulty": "선택한 암장의 난이도가 아닙니다."}
            )

        climb_log = attrs.get("climb_log", getattr(self.instance, "climb_log", None))
        if climb_log is not None:
            if climb_log.user_id != request.user.id:
                raise serializers.ValidationError(
                    {"climb_log": "본인의 등반 기록만 연결할 수 있습니다."}
                )
            if climb_log.gym_id != gym.id:
                raise serializers.ValidationError(
                    {"climb_log": "같은 암장의 등반 기록만 연결할 수 있습니다."}
                )
        return attrs


class BetaSectorSerializer(serializers.Serializer):
    """암장 섹터 집계 응답 — beta_services.beta_sectors 결과."""

    sector = serializers.CharField()
    count = serializers.IntegerField()
