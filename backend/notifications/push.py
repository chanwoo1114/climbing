"""Web Push 팬아웃 — deliver_notification 태스크가 WebSocket 다음에 부른다.

VAPID 키(settings.WEBPUSH_VAPID_*)가 비어 있으면 아무것도 하지 않는다. 받는 회원의
NotificationSetting.push_enabled 가 False 면 건너뛰고(행이 없으면 기본 True), 살아 있는
구독마다 한 번씩 보낸다. 푸시 서비스가 404/410 을 돌려주면 구독이 만료·해지된 것이므로
행을 hard_delete 하고, 그 밖의 실패는 로그만 남긴다 — 어떤 경우에도 예외를 밖으로
내지 않는다 (인앱 알림은 이미 저장·전달됐다).

``_send_webpush`` 는 테스트에서 ``mock.patch("notifications.push._send_webpush")``
로 바꿔치기할 수 있게 모듈 함수로 둔다. pywebpush 는 이 함수 안에서 lazy import.
"""

import json
import logging

from django.conf import settings
from django.utils import timezone

from notifications.models import Notification, NotificationSetting, PushSubscription

logger = logging.getLogger(__name__)

# 푸시 서비스가 "이 구독은 더 이상 유효하지 않다" 는 뜻으로 쓰는 상태 코드.
GONE_STATUS_CODES = frozenset({404, 410})

# 알림 이동 대상 → 프론트 라우트. NotificationSerializer 의 target_type/target_id 와 같다.
_TARGET_PATHS = {
    Notification.TargetType.CLIMB_LOG: "/logs/{id}",
    Notification.TargetType.POST: "/posts/{id}",
    Notification.TargetType.RECRUITMENT: "/posts/{id}",
    Notification.TargetType.CREW: "/crews/{id}",
    Notification.TargetType.USER: "/users/{id}",
}


def is_configured() -> bool:
    return bool(
        settings.WEBPUSH_VAPID_PUBLIC_KEY and settings.WEBPUSH_VAPID_PRIVATE_KEY
    )


def target_path(target_type: str, target_id: int) -> str:
    """알림을 눌렀을 때 열 프론트 경로. 모르는 종류면 알림 목록으로."""
    template = _TARGET_PATHS.get(target_type)
    if template is None:
        return "/notifications"
    return template.format(id=target_id)


def target_url(target_type: str, target_id: int) -> str:
    return f"{settings.FRONTEND_BASE_URL}{target_path(target_type, target_id)}"


def build_payload(notification: Notification) -> dict:
    """서비스 워커가 받는 JSON. 문구는 이미 렌더링돼 있으니 그대로 보여 주면 된다."""
    return {
        "id": notification.id,
        "type": notification.type,
        "message": notification.message,
        "target_type": notification.target_type,
        "target_id": notification.target_id,
        "url": target_url(notification.target_type, notification.target_id),
        "created_at": notification.created_at.isoformat(),
    }


def push_allowed(user_id: int) -> bool:
    setting = (
        NotificationSetting.objects.filter(user_id=user_id)
        .values_list("push_enabled", flat=True)
        .first()
    )
    return True if setting is None else setting


def vapid_claims() -> dict:
    """sub 는 mailto: URI 여야 한다. .env 에 'mailto:' 없이 적어도 붙여 준다."""
    email = settings.WEBPUSH_VAPID_CLAIMS_EMAIL.strip()
    if email and not email.startswith("mailto:"):
        email = f"mailto:{email}"
    return {"sub": email}


def _send_webpush(subscription: PushSubscription, payload: dict) -> None:
    """구독 하나에 실제 발송. 실패는 pywebpush.WebPushException 으로 올라온다."""
    from pywebpush import webpush

    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
        vapid_claims=vapid_claims(),
        ttl=settings.WEBPUSH_TTL_SECONDS,
    )


def _is_gone(exc: Exception) -> bool:
    from pywebpush import WebPushException

    if not isinstance(exc, WebPushException):
        return False
    status_code = getattr(exc.response, "status_code", None)
    return status_code in GONE_STATUS_CODES


def send_push(notification: Notification) -> int:
    """받는 회원의 살아 있는 구독 전부에 발송. 성공한 건수를 돌려준다 (예외 없음)."""
    if not is_configured() or not push_allowed(notification.recipient_id):
        return 0

    payload = build_payload(notification)
    sent = 0
    for subscription in PushSubscription.objects.filter(
        user_id=notification.recipient_id
    ):
        try:
            _send_webpush(subscription, payload)
        except Exception as exc:  # noqa: BLE001 — 구독 하나의 실패가 나머지를 막지 않게
            if _is_gone(exc):
                logger.info(
                    "push subscription gone, removing: id=%s user=%s",
                    subscription.id,
                    subscription.user_id,
                )
                subscription.hard_delete()
            else:
                logger.exception(
                    "web push failed: subscription=%s notification=%s",
                    subscription.id,
                    notification.id,
                )
            continue
        sent += 1
        subscription.last_used_at = timezone.now()
        subscription.save(update_fields=["last_used_at", "updated_at"])
    return sent
