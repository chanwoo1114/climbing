"""이메일 팬아웃 — deliver_notification 태스크가 WebSocket·푸시 다음에 부른다.

좋아요·댓글·팔로우처럼 잦은 알림은 메일로 보내지 않고, 모집 마감·참여 승인/거절·크루
승인/거절처럼 놓치면 곤란한 종류(EMAIL_TYPES)만 보낸다. 조건은 전부 AND:

    settings.NOTIFICATION_EMAIL_ENABLED       전체 스위치
    NotificationSetting.email_enabled         회원별 스위치 (행 없으면 True)
    recipient.email_verified_at               인증 안 된 주소로는 보내지 않는다
    notification.type in EMAIL_TYPES

발송 자체는 accounts.tasks.send_email_task(Celery) 가 맡고, 템플릿은
notifications/templates/notifications/email/notification.{txt,html}
(accounts 메일과 같은 레이아웃).
"""

import logging

from django.conf import settings
from django.template.loader import render_to_string

from accounts.tasks import send_email_task
from notifications.models import Notification, NotificationSetting
from notifications.push import target_url

logger = logging.getLogger(__name__)

EMAIL_TYPES = frozenset(
    {
        Notification.Type.RECRUITMENT_CLOSED,
        Notification.Type.RECRUITMENT_APPROVED,
        Notification.Type.RECRUITMENT_REJECTED,
        Notification.Type.CREW_APPROVED,
        Notification.Type.CREW_REJECTED,
    }
)

SUBJECT_PREFIX = "[Climbing] "
# 제목은 짧게 — 긴 문구(마감 안내 등)는 앞부분만 두고 본문에서 전문을 보여 준다.
SUBJECT_MAX_LENGTH = 60


def build_subject(message: str) -> str:
    text = " ".join(message.split())
    if len(text) > SUBJECT_MAX_LENGTH:
        text = text[: SUBJECT_MAX_LENGTH - 1] + "…"
    return SUBJECT_PREFIX + text


def email_allowed(user_id: int) -> bool:
    setting = (
        NotificationSetting.objects.filter(user_id=user_id)
        .values_list("email_enabled", flat=True)
        .first()
    )
    return True if setting is None else setting


def should_email(notification: Notification) -> bool:
    recipient = notification.recipient
    return bool(
        settings.NOTIFICATION_EMAIL_ENABLED
        and notification.type in EMAIL_TYPES
        and recipient.email_verified_at is not None
        and recipient.email
        and email_allowed(recipient.id)
    )


def send_notification_email(notification: Notification) -> bool:
    """조건을 만족하면 메일 태스크를 큐에 넣고 True. 예외는 내지 않는다."""
    if not should_email(notification):
        return False

    recipient = notification.recipient
    subject = build_subject(notification.message)
    context = {
        "subject": subject,
        "preheader": notification.message,
        "nickname": recipient.nickname,
        "message": notification.message,
        "type_label": notification.get_type_display(),
        "link": target_url(notification.target_type, notification.target_id),
    }
    try:
        text = render_to_string("notifications/email/notification.txt", context)
        html = render_to_string("notifications/email/notification.html", context)
        send_email_task.delay(subject, text, [recipient.email], html)
    except Exception:  # noqa: BLE001 — 메일 실패는 인앱 알림과 무관
        logger.exception(
            "notification email failed: id=%s recipient=%s",
            notification.id,
            recipient.id,
        )
        return False
    return True
