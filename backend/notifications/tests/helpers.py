"""notifications 테스트 공용 헬퍼."""

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from chat.middleware import JWTAuthMiddleware
from chat.tests.helpers import IN_MEMORY_CHANNELS, access_token  # noqa: F401
from notifications.models import Notification
from notifications.routing import websocket_urlpatterns

# asgi.py 와 같은 구성에서 AllowedHostsOriginValidator 만 뺀 것 (Origin 헤더 불필요).
ws_application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))


def create_notification(recipient, actor=None, **kwargs) -> Notification:
    """서비스를 거치지 않고 행만 만든다 (API/WS 테스트용)."""
    defaults = {
        "type": Notification.Type.FOLLOW,
        "target_type": Notification.TargetType.USER,
        "target_id": actor.id if actor else 0,
        "message": "테스트 알림",
    }
    defaults.update(kwargs)
    return Notification.objects.create(recipient=recipient, actor=actor, **defaults)


def ws_communicator(user=None, token=None, application=ws_application):
    """알림 소켓 커뮤니케이터. user 를 주면 access 토큰을 자동으로 붙인다."""
    path = "/ws/notifications/"
    if token is None and user is not None:
        token = access_token(user)
    if token:
        path += f"?token={token}"
    return WebsocketCommunicator(application, path)
