"""다른 앱(community/crews)이 호출하는 서비스 함수 — 그룹 방 생성, 참여자 추가/제거, 1:1 재사용."""

from django.test import TestCase, override_settings
from rest_framework import serializers

from accounts.tests.helpers import create_verified_user
from chat.models import ChatRoom, ChatRoomMember, Message
from chat.services import (
    add_members,
    create_group_room,
    get_or_create_direct_room,
    post_system_message,
    remove_member,
    send_message,
)
from chat.tests.helpers import IN_MEMORY_CHANNELS


@override_settings(**IN_MEMORY_CHANNELS)
class GroupRoomServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="o@example.com", nickname="주최자")
        cls.a = create_verified_user(email="a@example.com", nickname="에이")
        cls.b = create_verified_user(email="b@example.com", nickname="비")

    def test_create_group_room_adds_creator_dedupes_and_posts_system_message(self):
        room = create_group_room(
            name="OO암장 투어",
            member_ids=[self.a.id, self.b.id, self.a.id],
            created_by=self.owner,
        )
        self.assertTrue(room.is_group)
        self.assertEqual(room.name, "OO암장 투어")
        self.assertEqual(room.created_by, self.owner)
        self.assertIsNone(room.direct_key)
        self.assertEqual(
            set(
                ChatRoomMember.objects.filter(room=room).values_list(
                    "user_id", flat=True
                )
            ),
            {self.owner.id, self.a.id, self.b.id},
        )
        messages = list(Message.objects.filter(room=room))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].type, "system")
        self.assertIsNone(messages[0].sender)
        self.assertEqual(messages[0].content, "OO암장 투어 채팅방이 생성되었습니다")

    def test_create_group_room_custom_system_message(self):
        room = create_group_room(
            name="크루",
            member_ids=[],
            created_by=self.owner,
            system_message="크루 단톡방이 열렸습니다",
        )
        self.assertEqual(
            Message.objects.get(room=room).content, "크루 단톡방이 열렸습니다"
        )
        self.assertEqual(ChatRoomMember.objects.filter(room=room).count(), 1)

    def test_add_members_is_idempotent_and_restores_left_member(self):
        room = create_group_room(name="방", member_ids=[], created_by=self.owner)
        added = add_members(room, [self.a.id, self.b.id])
        self.assertEqual({m.user_id for m in added}, {self.a.id, self.b.id})
        self.assertEqual(add_members(room, [self.a.id]), [])

        self.assertTrue(remove_member(room, self.a, "에이님이 나갔습니다"))
        self.assertFalse(ChatRoomMember.objects.filter(room=room, user=self.a).exists())
        self.assertEqual(
            Message.objects.filter(room=room).latest("id").content,
            "에이님이 나갔습니다",
        )
        self.assertFalse(remove_member(room, self.a))  # 이미 없음

        restored = add_members(room, [self.a.id])
        self.assertEqual([m.user_id for m in restored], [self.a.id])
        self.assertTrue(ChatRoomMember.objects.filter(room=room, user=self.a).exists())
        # 같은 (room, user) 행이 하나뿐 (UNIQUE 조건부 제약과 restore 가 맞물림)
        self.assertEqual(
            ChatRoomMember.all_objects.filter(room=room, user=self.a).count(), 1
        )

    def test_remove_member_without_system_message(self):
        room = create_group_room(
            name="방", member_ids=[self.a.id], created_by=self.owner
        )
        before = Message.objects.filter(room=room).count()
        self.assertTrue(remove_member(room, self.a))
        self.assertEqual(Message.objects.filter(room=room).count(), before)

    def test_send_message_and_post_system_message(self):
        room = create_group_room(
            name="방", member_ids=[self.a.id], created_by=self.owner
        )
        msg = send_message(room, self.a, "안녕")
        self.assertEqual(msg.type, "text")
        self.assertEqual(msg.sender, self.a)
        self.assertEqual(
            ChatRoomMember.objects.get(room=room, user=self.a).last_read_message_id,
            msg.id,
        )
        sys_msg = post_system_message(room, "공지")
        self.assertEqual(sys_msg.type, "system")
        self.assertIsNone(sys_msg.sender)


@override_settings(**IN_MEMORY_CHANNELS)
class DirectRoomServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = create_verified_user(email="a@example.com", nickname="에이")
        cls.b = create_verified_user(email="b@example.com", nickname="비")

    def test_reuses_room_regardless_of_order(self):
        room, created = get_or_create_direct_room(self.a, self.b)
        self.assertTrue(created)
        self.assertEqual(
            room.direct_key, f"{min(self.a.id, self.b.id)}:{max(self.a.id, self.b.id)}"
        )
        again, created = get_or_create_direct_room(self.b, self.a)
        self.assertFalse(created)
        self.assertEqual(again.id, room.id)
        self.assertEqual(ChatRoom.objects.count(), 1)
        self.assertEqual(ChatRoomMember.objects.filter(room=room).count(), 2)

    def test_self_chat_rejected(self):
        with self.assertRaises(serializers.ValidationError):
            get_or_create_direct_room(self.a, self.a)
        self.assertEqual(ChatRoom.objects.count(), 0)

    def test_soft_deleted_room_is_restored_instead_of_duplicated(self):
        room, _ = get_or_create_direct_room(self.a, self.b)
        room.delete()  # 방 + 참여자 cascade soft delete
        self.assertEqual(ChatRoom.objects.count(), 0)

        again, created = get_or_create_direct_room(self.a, self.b)
        self.assertFalse(created)
        self.assertEqual(again.id, room.id)
        self.assertFalse(again.is_deleted)
        self.assertEqual(ChatRoomMember.objects.filter(room=room).count(), 2)
        self.assertEqual(ChatRoom.all_objects.count(), 1)
