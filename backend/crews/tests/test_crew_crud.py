"""크루 — 목록/필터/검색, 생성(단톡방·크루장 소속), 상세(chat_room_id 노출), 수정/삭제 권한."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from chat.models import ChatRoom, ChatRoomMember, Message
from crews.models import Crew, CrewMember
from crews.tests.helpers import add_member, create_crew, create_gym


class CrewListCreateTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.other_gym = create_gym("다른암장")
        cls.url = reverse("v1:crews:crew-list")

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url, {"name": "x"}).status_code, 401)

    def test_list_newest_first_with_preview_counts_and_my_status(self):
        first = create_crew(self.owner, name="첫크루", description="가" * 300)
        second = create_crew(
            self.owner, name="둘째크루", home_gym=self.gym, join_type="approval"
        )
        add_member(second, self.user, status="pending")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual([c["id"] for c in results], [second.id, first.id])

        item = results[1]
        self.assertEqual(len(item["description"]), 100)
        self.assertIsNone(item["home_gym"])
        self.assertEqual(item["owner"], {"id": self.owner.id, "nickname": "alpha"})
        self.assertEqual(item["member_count"], 1)
        self.assertEqual(item["max_members"], 30)
        self.assertIsNone(item["my_status"])
        self.assertNotIn("chat_room_id", item)
        self.assertNotIn("is_feed_public", item)

        self.assertEqual(
            results[0]["home_gym"], {"id": self.gym.id, "name": "테스트암장"}
        )
        self.assertEqual(results[0]["my_status"], "pending")

        self.client.force_authenticate(self.owner)
        mine = self.client.get(self.url).json()["data"]["results"]
        self.assertEqual({c["my_status"] for c in mine}, {"owner"})

    def test_filter_by_gym_and_search(self):
        create_crew(self.owner, name="강남볼더링", home_gym=self.gym)
        create_crew(self.owner, name="홍대리드", home_gym=self.other_gym)

        by_gym = self.client.get(self.url, {"gym": self.gym.id}).json()
        self.assertEqual([c["name"] for c in by_gym["data"]["results"]], ["강남볼더링"])
        by_q = self.client.get(self.url, {"q": "리드"}).json()
        self.assertEqual([c["name"] for c in by_q["data"]["results"]], ["홍대리드"])
        self.assertEqual(self.client.get(self.url, {"gym": "abc"}).status_code, 400)

    def test_create_makes_chat_room_and_owner_membership(self):
        payload = {
            "name": "새크루",
            "description": "같이 올라요",
            "home_gym": self.gym.id,
            "join_type": "approval",
            "max_members": 10,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["name"], "새크루")
        self.assertEqual(data["my_status"], "owner")
        self.assertEqual(data["member_count"], 1)
        self.assertFalse(data["is_feed_public"])

        crew = Crew.objects.get(pk=data["id"])
        self.assertEqual(crew.owner_id, self.user.id)
        member = CrewMember.objects.get(crew=crew, user=self.user)
        self.assertEqual((member.role, member.status), ("owner", "active"))
        self.assertIsNotNone(member.joined_at)

        room = ChatRoom.objects.get(pk=crew.chat_room_id)
        self.assertTrue(room.is_group)
        self.assertEqual(room.name, "새크루")
        self.assertEqual(data["chat_room_id"], room.id)
        self.assertTrue(
            ChatRoomMember.objects.filter(room=room, user=self.user).exists()
        )
        self.assertEqual(Message.objects.filter(room=room, type="system").count(), 1)

    def test_create_rejects_duplicate_name_case_insensitively(self):
        create_crew(self.owner, name="Chalk")
        response = self.client.post(self.url, {"name": "chalk"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["error"]["fields"])

    def test_create_validates_fields(self):
        response = self.client.post(self.url, {"name": "", "max_members": 1})
        self.assertEqual(response.status_code, 400)
        fields = response.json()["error"]["fields"]
        self.assertIn("name", fields)
        self.assertIn("max_members", fields)

        response = self.client.post(self.url, {"name": "x", "max_members": 201})
        self.assertIn("max_members", response.json()["error"]["fields"])


class CrewDetailTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.staff = create_verified_user(email="b@example.com", nickname="bravo")
        cls.member = create_verified_user(email="c@example.com", nickname="charlie")
        cls.outsider = create_verified_user(email="d@example.com", nickname="delta")

    def setUp(self):
        self.crew = create_crew(self.owner, name="크루", description="긴 소개")
        add_member(self.crew, self.staff, role="staff")
        add_member(self.crew, self.member)
        self.url = reverse("v1:crews:crew-detail", args=[self.crew.id])

    def test_detail_shows_chat_room_only_to_active_members(self):
        self.client.force_authenticate(self.member)
        data = self.client.get(self.url).json()["data"]
        self.assertEqual(data["description"], "긴 소개")
        self.assertEqual(data["chat_room_id"], self.crew.chat_room_id)
        self.assertEqual(data["my_status"], "member")
        self.assertEqual(data["member_count"], 3)

        self.client.force_authenticate(self.outsider)
        data = self.client.get(self.url).json()["data"]
        self.assertIsNone(data["chat_room_id"])
        self.assertIsNone(data["my_status"])

        add_member(self.crew, self.outsider, status="pending")
        data = self.client.get(self.url).json()["data"]
        self.assertIsNone(data["chat_room_id"])
        self.assertEqual(data["my_status"], "pending")

    def test_unknown_or_deleted_crew_is_404(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.get(reverse("v1:crews:crew-detail", args=[99999])).status_code,
            404,
        )
        self.crew.delete()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_patch_allowed_for_owner_and_staff_only(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.patch(self.url, {"description": "x"}).status_code, 403
        )
        self.client.force_authenticate(self.outsider)
        self.assertEqual(
            self.client.patch(self.url, {"description": "x"}).status_code, 403
        )

        self.client.force_authenticate(self.staff)
        response = self.client.patch(
            self.url, {"description": "수정", "is_feed_public": True}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["description"], "수정")
        self.assertTrue(response.json()["data"]["is_feed_public"])

        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.url, {"name": "새이름"})
        self.assertEqual(response.status_code, 200)
        self.crew.refresh_from_db()
        self.assertEqual(self.crew.name, "새이름")
        self.assertEqual(self.crew.chat_room.name, "새이름")  # 단톡방 이름 동기화

    def test_patch_cannot_shrink_below_active_members(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.url, {"max_members": 2})
        self.assertEqual(response.status_code, 400)
        self.assertIn("max_members", response.json()["error"]["fields"])
        self.assertEqual(
            self.client.patch(self.url, {"max_members": 3}).status_code, 200
        )

    def test_delete_owner_only_and_soft_deletes_members(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.delete(self.url).status_code, 403)

        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertFalse(Crew.objects.filter(pk=self.crew.pk).exists())
        self.assertTrue(Crew.all_objects.get(pk=self.crew.pk).is_deleted)
        self.assertEqual(CrewMember.objects.filter(crew=self.crew).count(), 0)
        self.assertEqual(CrewMember.all_objects.filter(crew=self.crew).count(), 3)
        # 단톡방은 그대로 (대화 기록 보존)
        self.assertTrue(ChatRoom.objects.filter(pk=self.crew.chat_room_id).exists())
