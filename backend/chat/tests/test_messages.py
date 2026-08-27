"""메시지 목록/전송, 읽음 처리, 나가기 — 검증·권한·읽음 위치 규칙."""

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from chat.models import ChatRoomMember, Message
from chat.tests.helpers import (
    IN_MEMORY_CHANNELS,
    create_direct_room,
    create_group_room,
    create_message,
)


@override_settings(**IN_MEMORY_CHANNELS)
class MessageListCreateTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="me@example.com", nickname="나")
        cls.peer = create_verified_user(email="peer@example.com", nickname="상대")
        cls.other = create_verified_user(email="other@example.com", nickname="남")
        cls.room = create_direct_room(cls.me, cls.peer)
        cls.url = reverse("v1:chat:room-messages", args=[cls.room.id])

    def setUp(self):
        self.client.force_authenticate(self.me)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url, {"content": "x"}).status_code, 401)

    def test_non_member_gets_404(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {"content": "x"}).status_code, 404)
        self.assertEqual(Message.objects.count(), 0)

    def test_list_newest_first_with_cursor(self):
        ids = [create_message(self.room, self.peer, f"m{i}").id for i in range(5)]
        res = self.client.get(self.url, {"limit": 3})
        data = res.json()["data"]
        self.assertEqual([m["id"] for m in data["results"]], ids[::-1][:3])
        self.assertIsNotNone(data["next_cursor"])

        res = self.client.get(data["next_cursor"])
        self.assertEqual(
            [m["id"] for m in res.json()["data"]["results"]], ids[::-1][3:]
        )

    def test_post_creates_message_and_marks_own_read(self):
        res = self.client.post(self.url, {"content": "  안녕하세요  "})
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertEqual(data["content"], "안녕하세요")
        self.assertEqual(data["type"], "text")
        self.assertEqual(data["room_id"], self.room.id)
        self.assertEqual(data["sender"]["id"], self.me.id)
        self.assertEqual(data["sender"]["nickname"], "나")

        me = ChatRoomMember.objects.get(room=self.room, user=self.me)
        self.assertEqual(me.last_read_message_id, data["id"])
        peer = ChatRoomMember.objects.get(room=self.room, user=self.peer)
        self.assertIsNone(peer.last_read_message_id)

        # 상대 입장에서는 안 읽은 메시지 1개
        self.client.force_authenticate(self.peer)
        rooms = self.client.get(reverse("v1:chat:room-list")).json()["data"]["results"]
        self.assertEqual(rooms[0]["unread_count"], 1)

    def test_post_validation(self):
        self.assertEqual(self.client.post(self.url, {"content": ""}).status_code, 400)
        self.assertEqual(
            self.client.post(self.url, {"content": "   "}).status_code, 400
        )
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        res = self.client.post(self.url, {"content": "x" * 2001})
        self.assertEqual(res.status_code, 400)
        self.assertIn("2000", res.json()["error"]["message"])
        self.assertEqual(Message.objects.count(), 0)

        res = self.client.post(self.url, {"content": "x" * 2000})
        self.assertEqual(res.status_code, 201)


@override_settings(**IN_MEMORY_CHANNELS)
class MarkReadTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="me@example.com", nickname="나")
        cls.peer = create_verified_user(email="peer@example.com", nickname="상대")
        cls.other = create_verified_user(email="other@example.com", nickname="남")
        cls.room = create_direct_room(cls.me, cls.peer)
        cls.other_room = create_direct_room(cls.peer, cls.other)
        cls.m1 = create_message(cls.room, cls.peer, "1")
        cls.m2 = create_message(cls.room, cls.peer, "2")
        cls.foreign = create_message(cls.other_room, cls.other, "x")
        cls.url = reverse("v1:chat:room-read", args=[cls.room.id])

    def setUp(self):
        self.client.force_authenticate(self.me)

    def _last_read(self):
        return ChatRoomMember.objects.get(
            room=self.room, user=self.me
        ).last_read_message_id

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        res = self.client.post(self.url, {"message_id": self.m1.id})
        self.assertEqual(res.status_code, 401)

    def test_non_member_gets_404(self):
        self.client.force_authenticate(self.other)
        res = self.client.post(self.url, {"message_id": self.m1.id})
        self.assertEqual(res.status_code, 404)

    def test_mark_read_never_goes_backwards(self):
        res = self.client.post(self.url, {"message_id": self.m2.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["message_id"], self.m2.id)
        self.assertEqual(self._last_read(), self.m2.id)

        res = self.client.post(self.url, {"message_id": self.m1.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["message_id"], self.m2.id)
        self.assertEqual(self._last_read(), self.m2.id)

        rooms = self.client.get(reverse("v1:chat:room-list")).json()["data"]["results"]
        self.assertEqual(rooms[0]["unread_count"], 0)

    def test_message_from_other_room_rejected(self):
        res = self.client.post(self.url, {"message_id": self.foreign.id})
        self.assertEqual(res.status_code, 400)
        self.assertIsNone(self._last_read())

    def test_invalid_payload(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"message_id": 0}).status_code, 400)


@override_settings(**IN_MEMORY_CHANNELS)
class LeaveRoomTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="me@example.com", nickname="나")
        cls.peer = create_verified_user(email="peer@example.com", nickname="상대")
        cls.other = create_verified_user(email="other@example.com", nickname="남")
        cls.group = create_group_room("주말 투어", cls.me, cls.peer)
        cls.direct = create_direct_room(cls.me, cls.peer)

    def setUp(self):
        self.client.force_authenticate(self.me)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        url = reverse("v1:chat:room-leave", args=[self.group.id])
        self.assertEqual(self.client.delete(url).status_code, 401)

    def test_leave_group_posts_system_message(self):
        url = reverse("v1:chat:room-leave", args=[self.group.id])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(
            ChatRoomMember.objects.filter(room=self.group, user=self.me).exists()
        )
        self.assertTrue(
            ChatRoomMember.all_objects.filter(
                room=self.group, user=self.me, is_deleted=True
            ).exists()
        )
        last = Message.objects.filter(room=self.group).latest("id")
        self.assertEqual(last.type, "system")
        self.assertIsNone(last.sender)
        self.assertEqual(last.content, "나님이 나갔습니다")

        # 나간 뒤에는 방이 안 보인다
        self.assertEqual(self.client.delete(url).status_code, 404)
        detail = reverse("v1:chat:room-detail", args=[self.group.id])
        self.assertEqual(self.client.get(detail).status_code, 404)

    def test_cannot_leave_direct_room(self):
        url = reverse("v1:chat:room-leave", args=[self.direct.id])
        self.assertEqual(self.client.delete(url).status_code, 400)
        self.assertTrue(
            ChatRoomMember.objects.filter(room=self.direct, user=self.me).exists()
        )

    def test_non_member_gets_404(self):
        self.client.force_authenticate(self.other)
        url = reverse("v1:chat:room-leave", args=[self.group.id])
        self.assertEqual(self.client.delete(url).status_code, 404)
