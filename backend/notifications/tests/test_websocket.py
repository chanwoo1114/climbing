"""알림 WebSocket — JWT 인증, 접속 시 unread_count, notify → 소켓 이벤트, 남에겐 안 감.

TransactionTestCase + InMemory 채널 레이어 (chat/tests/test_websocket.py 와 같은 이유).
notify() 의 on_commit 은 autocommit 이라 즉시 실행되고, 테스트 설정은
CELERY_TASK_ALWAYS_EAGER 라 deliver_notification 이 그 자리에서 group_send 한다.
"""

from channels.db import database_sync_to_async
from django.test import TransactionTestCase, override_settings

from accounts.tests.helpers import create_verified_user
from climbs.tests.helpers import create_gym, create_log
from notifications.consumers import CLOSE_UNAUTHENTICATED
from notifications.services import notify_follow, notify_like
from notifications.tests.helpers import (
    IN_MEMORY_CHANNELS,
    create_notification,
    ws_communicator,
)
from social.models import Follow


@override_settings(**IN_MEMORY_CHANNELS)
class NotificationWebSocketTests(TransactionTestCase):
    def setUp(self):
        self.me = create_verified_user(email="me@example.com", nickname="나")
        self.actor = create_verified_user(email="actor@example.com", nickname="상대")
        self.other = create_verified_user(email="other@example.com", nickname="남")
        self.gym = create_gym()
        self.log = create_log(self.me, self.gym)

    async def _connect(self, user):
        comm = ws_communicator(user=user)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        return comm

    async def test_rejects_without_token(self):
        comm = ws_communicator()
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, CLOSE_UNAUTHENTICATED)

    async def test_rejects_invalid_token(self):
        comm = ws_communicator(token="not-a-jwt")
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, CLOSE_UNAUTHENTICATED)

    async def test_sends_unread_count_on_connect(self):
        await database_sync_to_async(create_notification)(self.me, self.actor)
        await database_sync_to_async(create_notification)(
            self.me, self.actor, is_read=True
        )
        await database_sync_to_async(create_notification)(self.other, self.actor)
        comm = await self._connect(self.me)
        try:
            self.assertEqual(
                await comm.receive_json_from(), {"type": "unread_count", "count": 1}
            )
        finally:
            await comm.disconnect()

    async def test_receives_notification_event_on_notify(self):
        mine = await self._connect(self.me)
        theirs = await self._connect(self.other)
        try:
            await mine.receive_json_from()  # unread_count
            await theirs.receive_json_from()

            n = await database_sync_to_async(notify_like)(self.log, self.actor)

            event = await mine.receive_json_from()
            self.assertEqual(event["type"], "notification")
            payload = event["notification"]
            self.assertEqual(payload["id"], n.id)
            self.assertEqual(payload["type"], "like")
            self.assertEqual(payload["actor"]["nickname"], "상대")
            self.assertEqual(payload["target_type"], "climb_log")
            self.assertEqual(payload["target_id"], self.log.id)
            self.assertEqual(payload["message"], "상대님이 회원님의 기록을 좋아합니다")
            self.assertFalse(payload["is_read"])
            self.assertTrue(await theirs.receive_nothing())  # 남의 알림은 안 온다
        finally:
            await mine.disconnect()
            await theirs.disconnect()

    async def test_event_reaches_every_socket_of_the_same_user(self):
        a = await self._connect(self.me)
        b = await self._connect(self.me)
        try:
            await a.receive_json_from()
            await b.receive_json_from()
            follow = await database_sync_to_async(Follow.objects.create)(
                follower=self.actor, following=self.me
            )
            await database_sync_to_async(notify_follow)(follow)
            for comm in (a, b):
                event = await comm.receive_json_from()
                self.assertEqual(event["notification"]["type"], "follow")
        finally:
            await a.disconnect()
            await b.disconnect()

    async def test_unknown_input_returns_error(self):
        comm = await self._connect(self.me)
        try:
            await comm.receive_json_from()
            await comm.send_json_to({"type": "bogus"})
            event = await comm.receive_json_from()
            self.assertEqual(event["type"], "error")
            self.assertEqual(event["code"], "unknown_type")
        finally:
            await comm.disconnect()

    async def test_full_asgi_application_routes_websocket(self):
        """config.asgi 의 실제 라우팅(JWTAuthMiddleware + chat 패턴과 합침)으로도 연결된다."""
        from config.asgi import application

        comm = ws_communicator(user=self.me, application=application)
        comm.scope["headers"] = [(b"origin", b"http://localhost")]
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        self.assertEqual((await comm.receive_json_from())["type"], "unread_count")
        await comm.disconnect()
