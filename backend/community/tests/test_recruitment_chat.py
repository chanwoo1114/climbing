from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from chat.models import ChatRoom, ChatRoomMember, Message
from community.models import Recruitment
from community.tests.helpers import add_participant, create_recruit_post
from gyms.models import Gym


class RecruitmentCloseCreatesChatRoomTests(APITestCase):
    """모집 마감 → 작성자 + 승인 참여자로 그룹 채팅방 생성 (docs/개발정의.md 4장 플로우)."""

    def setUp(self):
        from django.contrib.gis.geos import Point

        self.author = create_verified_user(email="a@example.com", nickname="작성자")
        self.approved = create_verified_user(email="b@example.com", nickname="승인됨")
        self.pending = create_verified_user(email="c@example.com", nickname="대기중")
        self.gym = Gym.objects.create(
            name="테스트암장", address="서울", location=Point(127.0, 37.5, srid=4326)
        )
        self.post = create_recruit_post(
            self.author, self.gym, capacity=5, join_type="approval"
        )
        add_participant(self.post, self.approved, status="approved")
        add_participant(self.post, self.pending, status="pending")
        self.close_url = reverse("v1:community:recruitment-close", args=[self.post.id])

    def test_close_creates_group_room_with_author_and_approved(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(self.close_url)
        self.assertEqual(response.status_code, 200)

        rec = Recruitment.objects.get(post=self.post)
        self.assertIsNotNone(rec.chat_room_id)
        self.assertEqual(response.json()["data"]["chat_room_id"], rec.chat_room_id)

        room = ChatRoom.objects.get(pk=rec.chat_room_id)
        self.assertTrue(room.is_group)
        self.assertEqual(room.name, "테스트암장 투어")
        members = set(
            ChatRoomMember.objects.filter(room=room).values_list("user_id", flat=True)
        )
        self.assertEqual(members, {self.author.id, self.approved.id})  # 대기중은 제외

        system = Message.objects.filter(room=room, type="system").first()
        self.assertIsNotNone(system)
        self.assertIn("테스트암장 투어 채팅방이 생성되었습니다", system.content)

    def test_closed_recruitment_exposes_chat_room_in_detail(self):
        self.client.force_authenticate(self.author)
        self.client.post(self.close_url)
        detail = self.client.get(
            reverse("v1:community:post-detail", args=[self.post.id])
        )
        self.assertIsNotNone(detail.json()["data"]["recruitment"]["chat_room_id"])
