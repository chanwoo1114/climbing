from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import BaseModel

CREW_NAME_MAX_LENGTH = 30
CREW_MAX_MEMBERS_MIN = 2
CREW_MAX_MEMBERS_MAX = 200
CREW_MAX_MEMBERS_DEFAULT = 30


class Crew(BaseModel):
    """클라이밍 크루. 생성 시 그룹 채팅방(chat_room)이 함께 만들어지고 크루장이
    CrewMember(role=owner, status=active) 로 등록된다 (services.create_crew).
    """

    class JoinType(models.TextChoices):
        INSTANT = "instant", "즉시 가입"
        APPROVAL = "approval", "승인제"

    name = models.CharField(
        max_length=CREW_NAME_MAX_LENGTH,
        unique=True,
        db_comment="크루 이름 (중복 불가, 최대 30자)",
    )
    description = models.TextField(blank=True, db_comment="크루 소개")
    image = models.URLField(blank=True, db_comment="대표 이미지 URL (S3)")
    home_gym = models.ForeignKey(
        "gyms.Gym",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crews",
        db_comment="주 활동 암장 FK (선택). 암장이 지워지면 NULL",
    )
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="owned_crews",
        db_comment="크루장 FK",
    )
    join_type = models.CharField(
        max_length=10,
        choices=JoinType.choices,
        default=JoinType.INSTANT,
        db_comment="가입 방식 (instant 즉시 가입 / approval 운영진 승인제)",
    )
    max_members = models.PositiveSmallIntegerField(
        default=CREW_MAX_MEMBERS_DEFAULT,
        validators=[
            MinValueValidator(CREW_MAX_MEMBERS_MIN),
            MaxValueValidator(CREW_MAX_MEMBERS_MAX),
        ],
        db_comment="최대 인원 (크루장 포함, 2~200명)",
    )
    # 크루가 지워져도 대화 기록은 남겨야 하므로 방 삭제를 막는다.
    chat_room = models.OneToOneField(
        "chat.ChatRoom",
        on_delete=models.PROTECT,
        related_name="crew",
        db_comment="크루 단톡방 FK — 크루 생성 시 자동 생성",
    )
    is_feed_public = models.BooleanField(
        default=False,
        db_comment="크루 피드 공개 여부 (False 면 활동 중인 크루원만 조회)",
    )

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["home_gym", "-created_at"]),
        ]
        db_table_comment = "클라이밍 크루 — 이름 유일, 단톡방 1:1, 가입 방식/정원"

    def __str__(self):
        return self.name


class CrewMember(BaseModel):
    """크루 소속. 승인 대기(pending)와 활동 중(active) 만 있고, 탈퇴·강퇴·거절은
    soft delete 라 다시 신청하면 새 행이 생긴다.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "크루장"
        STAFF = "staff", "운영진"
        MEMBER = "member", "크루원"

    class Status(models.TextChoices):
        PENDING = "pending", "승인 대기"
        ACTIVE = "active", "활동 중"

    crew = models.ForeignKey(
        Crew, on_delete=models.CASCADE, related_name="members", db_comment="크루 FK"
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="crew_memberships",
        db_comment="회원 FK",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
        db_comment="역할 (owner 크루장 / staff 운영진 / member 크루원)",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_comment="상태 (pending 승인 대기 / active 활동 중)",
    )
    joined_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="가입(활동 시작) 시각. 승인 대기 중이면 NULL",
    )

    class Meta:
        constraints = [
            # 탈퇴·강퇴·거절은 soft delete 라 살아있는 행만 유일하면 된다.
            models.UniqueConstraint(
                fields=["crew", "user"],
                condition=models.Q(is_deleted=False),
                name="uniq_crew_member",
            )
        ]
        indexes = [
            models.Index(fields=["crew", "status"]),
            models.Index(fields=["user", "status"]),
        ]
        db_table_comment = (
            "크루 소속 — (크루, 회원) 유일, 역할/상태, 탈퇴분은 soft delete"
        )

    def __str__(self):
        return f"{self.user_id}@{self.crew_id} ({self.role}/{self.status})"

    @property
    def is_manager(self) -> bool:
        """크루장·운영진 (활동 중)."""
        return self.status == self.Status.ACTIVE and self.role in (
            self.Role.OWNER,
            self.Role.STAFF,
        )


# drf-spectacular ENUM_NAME_OVERRIDES 용 (settings 에서 문자열 경로로 참조)
CREW_JOIN_TYPE_CHOICES = Crew.JoinType.choices
