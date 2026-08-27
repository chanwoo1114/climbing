"""Channels 컨슈머. 프론트는 useChatSocket 훅으로만 접근한다.

연결: ws/chat/{room_id}/?token=<access JWT>
  - 토큰 없음/무효 → close 4401, 참여자 아님 → close 4403
수신(클라이언트→서버):
  {"type": "message", "content": "..."}   저장 + 방 전체 브로드캐스트
  {"type": "read", "message_id": N}       읽음 위치 갱신 (뒤로는 안 감)
  {"type": "typing"}                      저장 없이 방 전체에 전달
송신(서버→클라이언트):
  {"type": "message", "message": {...MessageSerializer}}
  {"type": "read", "user_id": N, "message_id": N}
  {"type": "typing", "user": {"id", "nickname"}}
  {"type": "error", "code": "...", "message": "..."}
REST 로 보낸 메시지도 services.broadcast 를 거쳐 같은 모양으로 내려온다.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from chat import services
from chat.serializers import MessageCreateSerializer, ReadSerializer

CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.member = None
        self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        self.group_name = services.room_group_name(self.room_id)

        if self.user is None or not self.user.is_authenticated:
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        self.member = await database_sync_to_async(services.get_membership)(
            self.room_id, self.user
        )
        if self.member is None:
            await self.close(code=CLOSE_FORBIDDEN)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if getattr(self, "member", None) is not None:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # --- 클라이언트 → 서버 ---------------------------------------------------

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            await self._error("invalid", "JSON 객체를 보내 주세요.")
            return
        kind = content.get("type")
        if kind == "message":
            await self._handle_message(content)
        elif kind == "read":
            await self._handle_read(content)
        elif kind == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.typing",
                    "user": {"id": self.user.id, "nickname": self.user.nickname},
                },
            )
        else:
            await self._error("unknown_type", f"알 수 없는 type: {kind!r}")

    async def _handle_message(self, content):
        serializer = MessageCreateSerializer(data=content)
        if not serializer.is_valid():
            await self._error("invalid", _first_error(serializer.errors))
            return
        # send_message 가 저장 후 그룹으로 브로드캐스트하므로 여기서 따로 보내지 않는다.
        await database_sync_to_async(services.send_message)(
            self.member.room, self.user, serializer.validated_data["content"]
        )

    async def _handle_read(self, content):
        serializer = ReadSerializer(data=content)
        if not serializer.is_valid():
            await self._error("invalid", _first_error(serializer.errors))
            return
        try:
            await database_sync_to_async(services.mark_read)(
                self.member, serializer.validated_data["message_id"]
            )
        except Exception as exc:  # serializers.ValidationError (다른 방 메시지)
            await self._error("invalid", _first_error(getattr(exc, "detail", exc)))

    async def _error(self, code: str, message: str):
        await self.send_json({"type": "error", "code": code, "message": message})

    # --- 그룹 이벤트 → 클라이언트 (services.broadcast 의 type 과 짝) -------------

    async def _push(self, payload: dict):
        """제거(chat.member_removed) 이후 큐에 남아 있던 이벤트는 버린다."""
        if self.member is not None:
            await self.send_json(payload)

    async def chat_message(self, event):
        await self._push({"type": "message", "message": event["message"]})

    async def chat_read(self, event):
        await self._push(
            {
                "type": "read",
                "user_id": event["user_id"],
                "message_id": event["message_id"],
            }
        )

    async def chat_typing(self, event):
        await self._push({"type": "typing", "user": event["user"]})

    async def chat_member_removed(self, event):
        """나가기/강퇴된 회원의 소켓은 끊는다."""
        if event["user_id"] == self.user.id and self.member is not None:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            self.member = None
            await self.close(code=CLOSE_FORBIDDEN)


def _first_error(errors) -> str:
    """serializer.errors / ValidationError.detail 에서 대표 메시지 하나."""
    if isinstance(errors, dict):
        for value in errors.values():
            return _first_error(value)
        return "요청을 처리할 수 없습니다."
    if isinstance(errors, (list, tuple)) and errors:
        return _first_error(errors[0])
    return str(errors)
