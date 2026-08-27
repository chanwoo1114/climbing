"""알림 WebSocket 컨슈머.

연결: ws/notifications/?token=<access JWT> (인증은 chat.middleware.JWTAuthMiddleware)
  - 토큰 없음/무효 → close 4401
  - 접속 직후 {"type": "unread_count", "count": N} 한 번 내려준다
송신(서버→클라이언트):
  {"type": "notification", "notification": {...NotificationSerializer}}
  {"type": "unread_count", "count": N}   접속 시
  {"type": "error", "code", "message"}   알 수 없는 입력
클라이언트→서버 입력은 없다 (읽음 처리는 REST). 그룹 이름은 user_{id}.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from notifications import services
from notifications.tasks import user_group_name

CLOSE_UNAUTHENTICATED = 4401


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.group_name = None
        if self.user is None or not self.user.is_authenticated:
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        self.group_name = user_group_name(self.user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        count = await database_sync_to_async(services.unread_count)(self.user)
        await self.send_json({"type": "unread_count", "count": count})

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type") if isinstance(content, dict) else None
        await self.send_json(
            {
                "type": "error",
                "code": "unknown_type",
                "message": f"알 수 없는 type: {kind!r}",
            }
        )

    # --- 그룹 이벤트 → 클라이언트 (tasks.deliver_notification 의 type 과 짝) ------

    async def notification(self, event):
        await self.send_json(
            {"type": "notification", "notification": event["notification"]}
        )
