from django.db import models

from common.models import BaseModel

MESSAGE_MAX_LENGTH = 200


class Notification(BaseModel):
    """인앱 알림 한 건. 생성은 services.notify() 만 사용한다 (본인 제외·중복 정리·전달).

    target_type/target_id 는 프론트가 눌렀을 때 이동할 대상 — climb_log 는 기록 상세,
    post 는 게시글(모집글) 상세, crew 는 크루 상세, user 는 프로필.
    """

    class Type(models.TextChoices):
        LIKE = "like", "좋아요"
        COMMENT = "comment", "댓글"
        REPLY = "reply", "답글"
        FOLLOW = "follow", "팔로우"
        RECRUITMENT_CLOSED = "recruitment_closed", "모집 마감"
        RECRUITMENT_APPROVED = "recruitment_approved", "모집 참여 승인"
        RECRUITMENT_REJECTED = "recruitment_rejected", "모집 참여 거절"
        CREW_APPROVED = "crew_approved", "크루 가입 승인"
        CREW_REJECTED = "crew_rejected", "크루 가입 거절"
        CREW_JOINED = "crew_joined", "크루 가입/신청 (운영진용)"

    class TargetType(models.TextChoices):
        CLIMB_LOG = "climb_log", "등반 기록"
        POST = "post", "게시글"
        RECRUITMENT = "recruitment", "모집"
        CREW = "crew", "크루"
        USER = "user", "회원"

    recipient = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_comment="받는 회원 FK",
    )
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="acted_notifications",
        db_comment="행위자 FK (좋아요 누른 사람 등). 시스템 알림이면 NULL",
    )
    type = models.CharField(
        max_length=30, choices=Type.choices, db_comment="알림 종류 (like/comment/…)"
    )
    target_type = models.CharField(
        max_length=20,
        choices=TargetType.choices,
        db_comment="이동 대상 종류 (climb_log/post/recruitment/crew/user)",
    )
    target_id = models.PositiveBigIntegerField(db_comment="이동 대상 id")
    message = models.CharField(
        max_length=MESSAGE_MAX_LENGTH,
        db_comment="렌더링된 한국어 알림 문구 (최대 200자)",
    )
    is_read = models.BooleanField(default=False, db_comment="읽음 여부")
    read_at = models.DateTimeField(null=True, blank=True, db_comment="읽은 시각")

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]
        db_table_comment = "인앱 알림 — 받는 회원/행위자/종류/이동 대상/문구/읽음"

    def __str__(self):
        return f"[{self.type}] → {self.recipient_id}: {self.message}"


# drf-spectacular ENUM_NAME_OVERRIDES 용 (settings 에서 문자열 경로로 참조)
NOTIFICATION_TYPE_CHOICES = Notification.Type.choices
