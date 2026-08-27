"""chat 테스트 공용 헬퍼.

REST/서비스 테스트도 메시지를 만들면 채널 레이어로 브로드캐스트하므로, Redis 대신
InMemoryChannelLayer 를 쓰도록 클래스마다 override_settings(**IN_MEMORY_CHANNELS) 를 건다.
"""

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import AccessToken

from chat.middleware import JWTAuthMiddleware
from chat.models import ChatRoom, ChatRoomMember, Message
from chat.routing import websocket_urlpatterns

IN_MEMORY_CHANNELS = {
    "CHANNEL_LAYERS": {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
}

# asgi.py 와 같은 구성에서 AllowedHostsOriginValidator 만 뺀 것 (Origin 헤더 불필요).
ws_application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))


def create_direct_room(user_a, user_b) -> ChatRoom:
    room = ChatRoom.objects.create(
        is_group=False,
        created_by=user_a,
        direct_key=ChatRoom.make_direct_key(user_a.id, user_b.id),
    )
    ChatRoomMember.objects.create(room=room, user=user_a)
    ChatRoomMember.objects.create(room=room, user=user_b)
    return room


def create_group_room(name, *users) -> ChatRoom:
    room = ChatRoom.objects.create(is_group=True, name=name, created_by=users[0])
    for user in users:
        ChatRoomMember.objects.create(room=room, user=user)
    return room


def create_message(room, sender, content="안녕") -> Message:
    return Message.objects.create(room=room, sender=sender, content=content)


def access_token(user) -> str:
    return str(AccessToken.for_user(user))


def ws_communicator(room_id, user=None, token=None, application=ws_application):
    """방 소켓 커뮤니케이터. user 를 주면 access 토큰을 자동으로 붙인다."""
    path = f"/ws/chat/{room_id}/"
    if token is None and user is not None:
        token = access_token(user)
    if token:
        path += f"?token={token}"
    return WebsocketCommunicator(application, path)
