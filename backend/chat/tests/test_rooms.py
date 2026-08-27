"""채팅방 목록/1:1 생성/상세 — 정렬·peer·last_message·unread, 쿼리 수, 권한."""

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from chat.models import ChatRoom, ChatRoomMember
from chat.tests.helpers import (
    IN_MEMORY_CHANNELS,
    create_direct_room,
    create_group_room,
    create_message,
)


@override_settings(**IN_MEMORY_CHANNELS)
class ChatRoomListTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="me@example.com", nickname="나")
        cls.peer = create_verified_user(email="peer@example.com", nickname="상대")
        cls.other = create_verified_user(email="other@example.com", nickname="남")
        cls.direct = create_direct_room(cls.me, cls.peer)
        cls.group = create_group_room("주말 투어", cls.me, cls.peer, cls.other)
        cls.stranger_room = create_group_room("남의 방", cls.peer, cls.other)
        cls.url = reverse("v1:chat:room-list")

    def setUp(self):
        self.client.force_authenticate(self.me)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_lists_only_my_rooms_with_peer_and_counts(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        results = res.json()["data"]["results"]
        self.assertEqual({r["id"] for r in results}, {self.direct.id, self.group.id})

        direct = next(r for r in results if r["id"] == self.direct.id)
        self.assertFalse(direct["is_group"])
        self.assertEqual(direct["peer"]["id"], self.peer.id)
        self.assertEqual(direct["peer"]["nickname"], "상대")
        self.assertEqual(direct["member_count"], 2)
        self.assertIsNone(direct["last_message"])
        self.assertEqual(direct["unread_count"], 0)

        group = next(r for r in results if r["id"] == self.group.id)
        self.assertTrue(group["is_group"])
        self.assertEqual(group["name"], "주말 투어")
        self.assertIsNone(group["peer"])
        self.assertEqual(group["member_count"], 3)

    def test_ordered_by_latest_message_with_last_message_and_unread(self):
        create_message(self.group, self.other, "그룹 먼저")
        latest = create_message(self.direct, self.peer, "DM 나중")
        create_message(self.direct, self.me, "내가 보낸 건 안 읽음에 안 셈")
        ChatRoomMember.objects.filter(room=self.direct, user=self.me).update(
            last_read_message_id=latest.id
        )
        # 상대가 하나 더 보내면 안 읽은 메시지 1개 (내 메시지는 last_read 이후지만 제외 안 함)
        newest = create_message(self.direct, self.peer, "새 메시지")

        results = self.client.get(self.url).json()["data"]["results"]
        self.assertEqual([r["id"] for r in results], [self.direct.id, self.group.id])

        direct = results[0]
        self.assertEqual(direct["last_message"]["id"], newest.id)
        self.assertEqual(direct["last_message"]["content"], "새 메시지")
        self.assertEqual(direct["last_message"]["type"], "text")
        self.assertEqual(direct["last_message"]["sender"]["nickname"], "상대")
        # last_read=latest 이후 메시지: 내 것 1 + 상대 것 1
        self.assertEqual(direct["unread_count"], 2)
        self.assertEqual(direct["last_read_message_id"], latest.id)

        group = results[1]
        self.assertEqual(group["last_message"]["content"], "그룹 먼저")
        self.assertEqual(group["unread_count"], 1)  # 아무것도 안 읽음

    def test_system_message_has_null_sender(self):
        from chat.services import post_system_message

        post_system_message(self.group, "누군가 나갔습니다")
        results = self.client.get(self.url).json()["data"]["results"]
        group = next(r for r in results if r["id"] == self.group.id)
        self.assertEqual(group["last_message"]["type"], "system")
        self.assertIsNone(group["last_message"]["sender"])

    def test_room_list_is_a_single_query(self):
        for i in range(3):
            create_message(self.group, self.other, f"m{i}")
            create_message(self.direct, self.peer, f"d{i}")
        # 방이 늘어도 쿼리 수가 늘지 않아야 한다 (N+1 없음).
        with self.assertNumQueries(1):
            res = self.client.get(self.url)
        self.assertEqual(len(res.json()["data"]["results"]), 2)

    def test_left_room_is_hidden(self):
        ChatRoomMember.objects.get(room=self.group, user=self.me).delete()
        results = self.client.get(self.url).json()["data"]["results"]
        self.assertEqual([r["id"] for r in results], [self.direct.id])

    def test_cursor_pagination(self):
        res = self.client.get(self.url, {"limit": 1})
        data = res.json()["data"]
        self.assertEqual(len(data["results"]), 1)
        self.assertIsNotNone(data["next_cursor"])


@override_settings(**IN_MEMORY_CHANNELS)
class DirectRoomTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="me@example.com", nickname="나")
        cls.peer = create_verified_user(email="peer@example.com", nickname="상대")
        cls.url = reverse("v1:chat:room-direct")

    def setUp(self):
        self.client.force_authenticate(self.me)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        res = self.client.post(self.url, {"user_id": self.peer.id})
        self.assertEqual(res.status_code, 401)

    def test_create_then_reuse(self):
        res = self.client.post(self.url, {"user_id": self.peer.id})
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertFalse(data["is_group"])
        self.assertEqual(data["peer"]["id"], self.peer.id)
        self.assertEqual(data["member_count"], 2)
        room_id = data["id"]

        # 상대가 요청해도 같은 방 (200)
        self.client.force_authenticate(self.peer)
        res = self.client.post(self.url, {"user_id": self.me.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["id"], room_id)
        self.assertEqual(res.json()["data"]["peer"]["id"], self.me.id)
        self.assertEqual(ChatRoom.objects.filter(is_group=False).count(), 1)

    def test_self_chat_rejected(self):
        res = self.client.post(self.url, {"user_id": self.me.id})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(ChatRoom.objects.count(), 0)

    def test_unknown_user_rejected(self):
        res = self.client.post(self.url, {"user_id": 999999})
        self.assertEqual(res.status_code, 400)

    def test_direct_key_is_unique_at_db_level(self):
        from django.db import IntegrityError

        key = ChatRoom.make_direct_key(self.peer.id, self.me.id)
        ChatRoom.objects.create(direct_key=key)
        with self.assertRaises(IntegrityError):
            ChatRoom.objects.create(direct_key=key)


@override_settings(**IN_MEMORY_CHANNELS)
class ChatRoomDetailTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="me@example.com", nickname="나")
        cls.peer = create_verified_user(email="peer@example.com", nickname="상대")
        cls.other = create_verified_user(email="other@example.com", nickname="남")
        cls.room = create_group_room("주말 투어", cls.me, cls.peer)
        cls.url = reverse("v1:chat:room-detail", args=[cls.room.id])

    def test_member_sees_members(self):
        self.client.force_authenticate(self.me)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["id"], self.room.id)
        self.assertEqual(data["name"], "주말 투어")
        self.assertEqual(
            {m["user"]["id"] for m in data["members"]}, {self.me.id, self.peer.id}
        )
        self.assertIn("last_read_message_id", data["members"][0])

    def test_non_member_gets_404(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
