"""가입/탈퇴 — 즉시 가입(단톡방 참여), 승인제 대기, 정원(crew_full), 중복(already_member),
크루장 탈퇴 불가(owner_cannot_leave), 대기 취소, 대표 크루 해제."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from chat.models import ChatRoomMember, Message
from crews.models import CrewMember
from crews.tests.helpers import add_member, create_crew


class CrewJoinTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.third = create_verified_user(email="c@example.com", nickname="charlie")

    def setUp(self):
        self.client.force_authenticate(self.user)

    @staticmethod
    def join_url(crew):
        return reverse("v1:crews:crew-join", args=[crew.id])

    def test_requires_auth(self):
        crew = create_crew(self.owner)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.join_url(crew)).status_code, 401)

    def test_instant_join_is_active_and_enters_chat_room(self):
        crew = create_crew(self.owner)
        response = self.client.post(self.join_url(crew))
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["role"], "member")
        self.assertEqual(data["user"]["nickname"], "bravo")
        self.assertIsNotNone(data["joined_at"])

        self.assertTrue(
            ChatRoomMember.objects.filter(room=crew.chat_room, user=self.user).exists()
        )
        last = Message.objects.filter(room=crew.chat_room).order_by("-id").first()
        self.assertEqual(last.type, "system")
        self.assertEqual(last.content, "bravo님이 가입했습니다")

        detail = self.client.get(
            reverse("v1:crews:crew-detail", args=[crew.id])
        ).json()["data"]
        self.assertEqual(detail["my_status"], "member")
        self.assertEqual(detail["member_count"], 2)

    def test_approval_join_is_pending_without_chat_room(self):
        crew = create_crew(self.owner, join_type="approval")
        response = self.client.post(self.join_url(crew))
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["joined_at"])
        self.assertFalse(
            ChatRoomMember.objects.filter(room=crew.chat_room, user=self.user).exists()
        )

    def test_duplicate_join_rejected(self):
        crew = create_crew(self.owner)
        self.client.post(self.join_url(crew))
        response = self.client.post(self.join_url(crew))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "already_member")

        pending = create_crew(self.owner, name="승인제", join_type="approval")
        self.client.post(self.join_url(pending))
        response = self.client.post(self.join_url(pending))
        self.assertEqual(response.json()["error"]["code"], "already_member")

    def test_full_crew_rejects_join(self):
        crew = create_crew(self.owner, max_members=2)
        add_member(crew, self.third)
        response = self.client.post(self.join_url(crew))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "crew_full")
        self.assertFalse(CrewMember.objects.filter(crew=crew, user=self.user).exists())

    def test_rejoin_after_leave_creates_new_row(self):
        crew = create_crew(self.owner)
        self.client.post(self.join_url(crew))
        self.client.delete(reverse("v1:crews:crew-leave", args=[crew.id]))
        response = self.client.post(self.join_url(crew))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            CrewMember.all_objects.filter(crew=crew, user=self.user).count(), 2
        )
        self.assertTrue(
            ChatRoomMember.objects.filter(room=crew.chat_room, user=self.user).exists()
        )


class CrewLeaveTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")

    def setUp(self):
        self.crew = create_crew(self.owner)
        self.url = reverse("v1:crews:crew-leave", args=[self.crew.id])
        self.client.force_authenticate(self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.delete(self.url).status_code, 401)

    def test_active_member_leaves_crew_and_chat_room(self):
        self.client.post(reverse("v1:crews:crew-join", args=[self.crew.id]))
        self.user.profile.main_crew = self.crew
        self.user.profile.save(update_fields=["main_crew", "updated_at"])

        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            CrewMember.objects.filter(crew=self.crew, user=self.user).exists()
        )
        self.assertFalse(
            ChatRoomMember.objects.filter(
                room=self.crew.chat_room, user=self.user
            ).exists()
        )
        last = Message.objects.filter(room=self.crew.chat_room).order_by("-id").first()
        self.assertEqual(last.content, "bravo님이 나갔습니다")
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.main_crew_id)

    def test_pending_member_just_cancels(self):
        add_member(self.crew, self.user, status="pending")
        before = Message.objects.filter(room=self.crew.chat_room).count()
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertFalse(
            CrewMember.objects.filter(crew=self.crew, user=self.user).exists()
        )
        self.assertEqual(
            Message.objects.filter(room=self.crew.chat_room).count(), before
        )

    def test_owner_cannot_leave(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "owner_cannot_leave")

    def test_non_member_cannot_leave(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "not_crew_member")
