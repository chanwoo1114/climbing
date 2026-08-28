from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from accounts.models import User
from crews.models import (
    CREW_MAX_MEMBERS_MAX,
    CREW_MAX_MEMBERS_MIN,
    CREW_NAME_MAX_LENGTH,
    Crew,
    CrewMember,
)
from crews.services import (
    DESCRIPTION_PREVIEW_LENGTH,
    active_count,
    create_crew,
    update_crew,
)
from gyms.models import Gym

DESCRIPTION_MAX_LENGTH = 2000


class CrewUserSerializer(serializers.ModelSerializer):
    """크루원/크루장 요약. image 는 프로필에서 (select_related user__profile 전제)."""

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


class CrewOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "nickname")
        read_only_fields = fields


class CrewGymSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gym
        fields = ("id", "name")
        read_only_fields = fields


class CrewSummarySerializer(serializers.ModelSerializer):
    """다른 앱(프로필 대표 크루, 크루 주최 모집)이 내려주는 {id, name}."""

    class Meta:
        model = Crew
        fields = ("id", "name")
        read_only_fields = fields


class MainCrewField(serializers.PrimaryKeyRelatedField):
    """쓰기는 pk, 읽기는 {id, name} 인 크루 참조 필드 (UserProfile.main_crew 용)."""

    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return CrewSummarySerializer(value).data


# --- 크루 ---------------------------------------------------------------------


def _my_status(obj) -> str | None:
    """annotated_crews 의 my_role/my_member_status → owner/staff/member/pending|None."""
    status = getattr(obj, "my_member_status", None)
    if status is None:
        return None
    if status == CrewMember.Status.PENDING:
        return "pending"
    return getattr(obj, "my_role", None)


class CrewListSerializer(serializers.ModelSerializer):
    """목록용 — 소개는 100자 preview. member_count/my_status 는 annotated_crews 주석값."""

    description = serializers.SerializerMethodField()
    home_gym = CrewGymSerializer(read_only=True, allow_null=True)
    owner = CrewOwnerSerializer(read_only=True)
    member_count = serializers.IntegerField(
        read_only=True, help_text="활동 중인 크루원 수 (크루장 포함)"
    )
    my_status = serializers.SerializerMethodField(
        help_text="내 상태: owner | staff | member | pending | null(미소속)"
    )

    class Meta:
        model = Crew
        fields = (
            "id",
            "name",
            "description",
            "image",
            "home_gym",
            "owner",
            "join_type",
            "member_count",
            "max_members",
            "my_status",
            "created_at",
        )
        read_only_fields = fields

    def get_description(self, obj) -> str:
        return obj.description[:DESCRIPTION_PREVIEW_LENGTH]

    def get_my_status(self, obj) -> str | None:
        return _my_status(obj)


class CrewSerializer(CrewListSerializer):
    """상세용 — 전체 소개, 피드 공개 여부, 활동 중인 크루원에게만 chat_room_id."""

    description = serializers.CharField(read_only=True)
    chat_room_id = serializers.SerializerMethodField(
        help_text="크루 단톡방 id. 활동 중인 크루원이 아니면 null"
    )

    class Meta(CrewListSerializer.Meta):
        fields = CrewListSerializer.Meta.fields + (
            "is_feed_public",
            "chat_room_id",
            "updated_at",
        )
        read_only_fields = fields

    def get_chat_room_id(self, obj) -> int | None:
        if getattr(obj, "my_member_status", None) == CrewMember.Status.ACTIVE:
            return obj.chat_room_id
        return None


class CrewWriteSerializer(serializers.ModelSerializer):
    """생성/수정 입력. 응답은 CrewSerializer 로 다시 내려준다."""

    name = serializers.CharField(
        max_length=CREW_NAME_MAX_LENGTH,
        trim_whitespace=True,
        validators=[
            UniqueValidator(
                # all_objects: DB UNIQUE 는 soft delete 를 구분하지 않는다.
                queryset=Crew.all_objects.all(),
                message="이미 사용 중인 크루 이름입니다.",
                lookup="iexact",
            )
        ],
        error_messages={
            "blank": "크루 이름을 입력해 주세요.",
            "max_length": f"크루 이름은 {CREW_NAME_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    description = serializers.CharField(
        allow_blank=True,
        required=False,
        max_length=DESCRIPTION_MAX_LENGTH,
        error_messages={
            "max_length": f"크루 소개는 {DESCRIPTION_MAX_LENGTH}자 이하여야 합니다."
        },
    )
    image = serializers.URLField(allow_blank=True, required=False)
    home_gym = serializers.PrimaryKeyRelatedField(
        queryset=Gym.objects.all(),
        allow_null=True,
        required=False,
        error_messages={"does_not_exist": "존재하지 않는 암장입니다."},
    )
    max_members = serializers.IntegerField(
        required=False,
        min_value=CREW_MAX_MEMBERS_MIN,
        max_value=CREW_MAX_MEMBERS_MAX,
        error_messages={
            "min_value": f"최대 인원은 {CREW_MAX_MEMBERS_MIN}명 이상이어야 합니다.",
            "max_value": f"최대 인원은 {CREW_MAX_MEMBERS_MAX}명 이하여야 합니다.",
        },
    )

    class Meta:
        model = Crew
        fields = (
            "name",
            "description",
            "image",
            "home_gym",
            "join_type",
            "max_members",
            "is_feed_public",
        )

    def validate_max_members(self, value):
        crew = self.instance
        if crew is not None:
            members = active_count(crew)
            if value < members:
                raise serializers.ValidationError(
                    f"이미 {members}명이 활동 중이라 최대 인원을 그보다 줄일 수 없습니다."
                )
        return value

    def create(self, validated_data):
        return create_crew(self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        return update_crew(instance, **validated_data)


# --- 크루원 -------------------------------------------------------------------


class CrewMemberSerializer(serializers.ModelSerializer):
    user = CrewUserSerializer(read_only=True)

    class Meta:
        model = CrewMember
        fields = ("id", "user", "role", "status", "joined_at", "created_at")
        read_only_fields = fields


class CrewOwnerTransferSerializer(serializers.Serializer):
    """크루장 위임 입력 — 새 크루장 회원 id."""

    user_id = serializers.IntegerField(min_value=1)


class CrewMemberUpdateSerializer(serializers.Serializer):
    """크루장/운영진의 크루원 관리 입력 — status(승인/거절) 또는 role(역할) 중 하나."""

    status = serializers.ChoiceField(
        choices=[(CrewMember.Status.ACTIVE, "승인"), ("rejected", "거절")],
        required=False,
        error_messages={"invalid_choice": "status 는 active 또는 rejected 입니다."},
    )
    role = serializers.ChoiceField(
        choices=[
            (CrewMember.Role.STAFF, "운영진"),
            (CrewMember.Role.MEMBER, "크루원"),
        ],
        required=False,
        error_messages={"invalid_choice": "role 은 staff 또는 member 입니다."},
    )

    def validate(self, attrs):
        if ("status" in attrs) == ("role" in attrs):
            raise serializers.ValidationError(
                {"detail": "status 또는 role 중 하나만 보내야 합니다."}
            )
        return attrs


# ---- 통계 / 랭킹 (crews/stats.py 결과 — 읽기 전용 스키마) ---------------------


class MonthQuerySerializer(serializers.Serializer):
    """?month=YYYY-MM (없으면 이번 달). 파싱은 climbs.stats.parse_month."""

    month = serializers.CharField(required=False, help_text="YYYY-MM, 기본 이번 달")


class RankedUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nickname = serializers.CharField()
    image = serializers.CharField(allow_null=True)


class CrewMemberRankSerializer(serializers.Serializer):
    rank = serializers.IntegerField(help_text="동점은 같은 순위 (1,1,3)")
    user = RankedUserSerializer()
    log_count = serializers.IntegerField()
    success_count = serializers.IntegerField()


class CrewStatsSerializer(serializers.Serializer):
    """크루 월간 통계 — 활동 중 크루원들의 공개 기록만 집계."""

    month = serializers.CharField(help_text="YYYY-MM")
    member_count = serializers.IntegerField(help_text="활동 중 크루원 수")
    active_member_count = serializers.IntegerField(
        help_text="이 달 기록이 있는 크루원 수"
    )
    log_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    success_rate = serializers.FloatField(help_text="0~100")
    gym_count = serializers.IntegerField()
    ranking = CrewMemberRankSerializer(many=True, help_text="완등 수 순 상위 10명")


class RankedGymSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class RankedCrewSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    image = serializers.CharField(allow_null=True)
    home_gym = RankedGymSerializer(allow_null=True)


class CrewRankSerializer(serializers.Serializer):
    rank = serializers.IntegerField(help_text="동점은 같은 순위 (1,1,3)")
    crew = RankedCrewSerializer()
    member_count = serializers.IntegerField()
    log_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
