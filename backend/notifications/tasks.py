"""알림 전달 태스크 — 저장(services.notify) 후 on_commit 으로 큐에 들어간다.

지금은 WebSocket(채널 레이어 그룹 ``user_{id}``) 으로만 밀어준다. 푸시·이메일 팬아웃은
이 태스크에 덧붙인다. 테스트는 CELERY_TASK_ALWAYS_EAGER 라 즉시 실행된다.
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
    from notifications.models import Notification
    from notifications.serializers import NotificationSerializer

    notification = (
        Notification.objects.select_related("actor__profile")
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
        logger.exception("notification push failed: id=%s", notification_id)
        return
    logger.info(
        "notification delivered: id=%s recipient=%s type=%s",
        notification_id,
        notification.recipient_id,
        notification.type,
    )
