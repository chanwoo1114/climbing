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
        CREW_OWNER = "crew_owner", "크루장 위임"
        ANALYSIS_DONE = "analysis_done", "자세 분석 완료"
        ANALYSIS_FAILED = "analysis_failed", "자세 분석 실패"
        REPORT_DONE = "report_done", "코칭 리포트 완료"
        REPORT_FAILED = "report_failed", "코칭 리포트 실패"

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


class NotificationSetting(BaseModel):
    """회원별 알림 채널 스위치. 행이 없으면 둘 다 켜진 것으로 본다 (services.get_or_create_setting).

    인앱(WebSocket) 알림은 항상 가고, 여기서는 푸시·이메일 팬아웃만 끈다.
    """

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notification_setting",
        db_comment="회원 FK (1:1)",
    )
    push_enabled = models.BooleanField(
        default=True, db_comment="Web Push 팬아웃 허용 여부"
    )
    email_enabled = models.BooleanField(
        default=True, db_comment="이메일 팬아웃 허용 여부 (중요 알림만 발송)"
    )

    class Meta:
        db_table_comment = "회원별 알림 채널 설정 — 푸시/이메일 on·off"

    def __str__(self):
        return (
            f"setting(user={self.user_id}, push={self.push_enabled}, "
            f"email={self.email_enabled})"
        )


class PushSubscription(BaseModel):
    """브라우저 Web Push 구독 (PushSubscription.toJSON() 의 endpoint + keys).

    같은 브라우저가 다른 계정으로 다시 구독하면 endpoint 가 같으므로 살아 있는 행 중
    endpoint 로 upsert 한다(services.subscribe_push). 해지·만료(404/410)는 soft delete 가
    아니라 hard_delete — 죽은 endpoint 를 남겨 둘 이유가 없고, 조건부 unique 는
    is_deleted=False 만 보므로 어느 쪽이든 재구독은 가능하다.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        db_comment="구독한 회원 FK",
    )
    endpoint = models.URLField(
        max_length=500, db_comment="푸시 서비스 endpoint URL (브라우저별 고유)"
    )
    p256dh = models.CharField(
        max_length=255, db_comment="클라이언트 공개키 (keys.p256dh, base64url)"
    )
    auth = models.CharField(
        max_length=255, db_comment="인증 비밀 (keys.auth, base64url)"
    )
    user_agent = models.CharField(
        max_length=255, blank=True, db_comment="구독 당시 User-Agent (기기 식별용)"
    )
    last_used_at = models.DateTimeField(
        null=True, blank=True, db_comment="마지막으로 푸시 발송에 성공한 시각"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["endpoint"],
                condition=models.Q(is_deleted=False),
                name="uniq_push_subscription_endpoint",
            )
        ]
        indexes = [models.Index(fields=["user"])]
        db_table_comment = "Web Push 구독 — 회원/endpoint/키/UA/마지막 사용"

    def __str__(self):
        return f"push(user={self.user_id}, endpoint={self.endpoint[:40]}…)"


# drf-spectacular ENUM_NAME_OVERRIDES 용 (settings 에서 문자열 경로로 참조)
NOTIFICATION_TYPE_CHOICES = Notification.Type.choices
