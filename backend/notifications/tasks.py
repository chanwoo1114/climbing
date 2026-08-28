"""알림 전달 태스크 — 저장(services.notify) 후 on_commit 으로 큐에 들어간다.

채널 세 개를 순서대로, 서로 독립적으로 시도한다 (하나가 실패해도 나머지는 간다):

    1. WebSocket  채널 레이어 그룹 ``user_{id}`` 로 group_send (항상)
    2. Web Push   notifications.push.send_push — VAPID 키가 있고 회원이 켜 둔 경우
    3. 이메일     notifications.emails.send_notification_email — 중요 종류만, 인증된 주소만

테스트는 CELERY_TASK_ALWAYS_EAGER 라 즉시 실행된다.
"""

import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def user_group_name(user_id: int) -> str:
    return f"user_{user_id}"


@shared_task
def deliver_notification(notification_id: int) -> None:
    from notifications.emails import send_notification_email
    from notifications.models import Notification
    from notifications.push import send_push
    from notifications.serializers import NotificationSerializer

    notification = (
        Notification.objects.select_related("actor__profile", "recipient")
        .filter(pk=notification_id)
        .first()
    )
    if notification is None:  # 전달 전에 삭제됨
        return

    payload = dict(NotificationSerializer(notification).data)
    try:
        async_to_sync(get_channel_layer().group_send)(
            user_group_name(notification.recipient_id),
            {"type": "notification", "notification": payload},
        )
    except Exception:  # noqa: BLE001 — 전달은 best-effort, 저장은 이미 끝났다
        logger.exception("notification websocket failed: id=%s", notification_id)
    else:
        logger.info(
            "notification delivered: id=%s recipient=%s type=%s",
            notification_id,
            notification.recipient_id,
            notification.type,
        )

    pushed = 0
    try:
        pushed = send_push(notification)
    except Exception:  # noqa: BLE001 — send_push 는 예외를 안 내지만 방어적으로
        logger.exception("notification push failed: id=%s", notification_id)

    emailed = False
    try:
        emailed = send_notification_email(notification)
    except Exception:  # noqa: BLE001
        logger.exception("notification email failed: id=%s", notification_id)

    if pushed or emailed:
        logger.info(
            "notification fan-out: id=%s push=%s email=%s",
            notification_id,
            pushed,
            emailed,
        )
