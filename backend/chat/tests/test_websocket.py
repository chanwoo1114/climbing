"""WebSocket — JWT 인증, 참여자 검사, 메시지 왕복, REST 전송이 소켓에 닿는지.

TransactionTestCase 를 쓰는 이유: channels 의 database_sync_to_async 는 앞뒤로
close_old_connections() 를 부르는데, TestCase 가 트랜잭션으로 감싼 커넥션을 닫아 버린다
(Channels 문서의 권장 사항). 채널 레이어는 InMemory 로 override.
"""

from channels.db import database_sync_to_async
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.tests.helpers import create_verified_user
from chat.consumers import CLOSE_FORBIDDEN, CLOSE_UNAUTHENTICATED
from chat.models import ChatRoomMember, Message
from chat.tests.helpers import (
    IN_MEMORY_CHANNELS,
    create_direct_room,
    create_group_room,
    ws_communicator,
)


@override_settings(**IN_MEMORY_CHANNELS)
class ChatWebSocketTests(TransactionTestCase):
    def setUp(self):
        self.me = create_verified_user(email="me@example.com", nickname="나")
        self.peer = create_verified_user(email="peer@example.com", nickname="상대")
        self.other = create_verified_user(email="other@example.com", nickname="남")
        self.room = create_direct_room(self.me, self.peer)
        self.group = create_group_room("그룹", self.me, self.peer)

    async def _connect(self, user, room=None):
        comm = ws_communicator((room or self.room).id, user=user)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        return comm

    async def test_rejects_without_token(self):
        comm = ws_communicator(self.room.id)
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, CLOSE_UNAUTHENTICATED)

    async def test_rejects_invalid_token(self):
        comm = ws_communicator(self.room.id, token="not-a-jwt")
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, CLOSE_UNAUTHENTICATED)

    async def test_rejects_non_member(self):
        comm = ws_communicator(self.room.id, user=self.other)
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, CLOSE_FORBIDDEN)

    async def test_rejects_unknown_room(self):
        comm = ws_communicator(999999, user=self.me)
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, CLOSE_FORBIDDEN)

    async def test_message_round_trip_between_two_clients(self):
        a = await self._connect(self.me)
        b = await self._connect(self.peer)
        try:
            await a.send_json_to({"type": "message", "content": "  안녕  "})
            for comm in (a, b):
                event = await comm.receive_json_from()
                self.assertEqual(event["type"], "message")
                self.assertEqual(event["message"]["content"], "안녕")
                self.assertEqual(event["message"]["type"], "text")
                self.assertEqual(event["message"]["room_id"], self.room.id)
                self.assertEqual(event["message"]["sender"]["id"], self.me.id)
                self.assertEqual(event["message"]["sender"]["nickname"], "나")

            message = await database_sync_to_async(Message.objects.get)(room=self.room)
            self.assertEqual(message.content, "안녕")
            me = await database_sync_to_async(ChatRoomMember.objects.get)(
                room=self.room, user=self.me
            )
            self.assertEqual(me.last_read_message_id, message.id)
        finally:
            await a.disconnect()
            await b.disconnect()

    async def test_invalid_message_returns_error_only_to_sender(self):
        a = await self._connect(self.me)
        b = await self._connect(self.peer)
        try:
            await a.send_json_to({"type": "message", "content": ""})
            event = await a.receive_json_from()
            self.assertEqual(event["type"], "error")
            self.assertEqual(event["code"], "invalid")
            self.assertTrue(await b.receive_nothing())

            await a.send_json_to({"type": "bogus"})
            self.assertEqual((await a.receive_json_from())["code"], "unknown_type")
            self.assertEqual(await database_sync_to_async(Message.objects.count)(), 0)
        finally:
            await a.disconnect()
            await b.disconnect()

    async def test_typing_is_broadcast_without_persistence(self):
        a = await self._connect(self.me)
        b = await self._connect(self.peer)
        try:
            await a.send_json_to({"type": "typing"})
            event = await b.receive_json_from()
            self.assertEqual(
                event, {"type": "typing", "user": {"id": self.me.id, "nickname": "나"}}
            )
            self.assertEqual(await database_sync_to_async(Message.objects.count)(), 0)
        finally:
            await a.disconnect()
            await b.disconnect()

    async def test_read_updates_last_read_and_notifies_room(self):
        a = await self._connect(self.me)
        b = await self._connect(self.peer)
        try:
            await a.send_json_to({"type": "message", "content": "읽어줘"})
            sent = (await a.receive_json_from())["message"]
            await b.receive_json_from()

            await b.send_json_to({"type": "read", "message_id": sent["id"]})
            for comm in (a, b):
                event = await comm.receive_json_from()
                self.assertEqual(
                    event,
                    {"type": "read", "user_id": self.peer.id, "message_id": sent["id"]},
                )
            peer = await database_sync_to_async(ChatRoomMember.objects.get)(
                room=self.room, user=self.peer
            )
            self.assertEqual(peer.last_read_message_id, sent["id"])

            # 다른 방 메시지 id → 오류
            await b.send_json_to({"type": "read", "message_id": 999999})
            self.assertEqual((await b.receive_json_from())["type"], "error")
        finally:
            await a.disconnect()
            await b.disconnect()

    async def test_rest_post_reaches_connected_socket(self):
        b = await self._connect(self.peer)
        try:
            client = APIClient()
            client.force_authenticate(self.me)
            url = reverse("v1:chat:room-messages", args=[self.room.id])
            res = await database_sync_to_async(client.post)(
                url, {"content": "REST 로 보냄"}
            )
            self.assertEqual(res.status_code, 201)

            event = await b.receive_json_from()
            self.assertEqual(event["type"], "message")
            self.assertEqual(event["message"]["id"], res.json()["data"]["id"])
            self.assertEqual(event["message"]["content"], "REST 로 보냄")
        finally:
            await b.disconnect()

    async def test_leaving_via_rest_closes_socket(self):
        a = await self._connect(self.me, room=self.group)
        b = await self._connect(self.peer, room=self.group)
        try:
            client = APIClient()
            client.force_authenticate(self.me)
            url = reverse("v1:chat:room-leave", args=[self.group.id])
            res = await database_sync_to_async(client.delete)(url)
            self.assertEqual(res.status_code, 204)

            # 남은 사람은 시스템 메시지를 받고, 나간 사람의 소켓은 닫힌다
            event = await b.receive_json_from()
            self.assertEqual(event["message"]["type"], "system")
            self.assertEqual(event["message"]["content"], "나님이 나갔습니다")

            output = await a.receive_output()
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], CLOSE_FORBIDDEN)
        finally:
            await a.disconnect()
            await b.disconnect()

    async def test_full_asgi_application_routes_websocket(self):
        """config.asgi 의 실제 라우팅(JWTAuthMiddleware 포함)으로도 연결된다."""
        from config.asgi import application

        comm = ws_communicator(self.room.id, user=self.me, application=application)
        comm.scope["headers"] = [(b"origin", b"http://localhost")]
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect()
