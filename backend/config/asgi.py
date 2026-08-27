import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Django 앱 로딩이 먼저 끝나야 채팅 라우팅에서 모델을 import 할 수 있다.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

# WebSocket 인증은 세션이 아니라 ?token=<access JWT> — chat/middleware.py
from chat.middleware import JWTAuthMiddleware  # noqa: E402
from chat.routing import websocket_urlpatterns as chat_patterns  # noqa: E402
from notifications.routing import (  # noqa: E402
    websocket_urlpatterns as notification_patterns,
)

# ws/chat/{room_id}/ + ws/notifications/
websocket_urlpatterns = [*chat_patterns, *notification_patterns]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
        ),
    }
)
