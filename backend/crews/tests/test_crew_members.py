"""크루원 관리 — 목록(active/pending 권한), 승인/거절(정원·단톡방), 역할 변경(크루장만),
강퇴(권한 계층·단톡방·대표 크루 해제)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from chat.models import ChatRoomMember, Message
from crews.models import CrewMember
from crews.tests.helpers import add_member, create_crew


class CrewMemberBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.staff = create_verified_user(email="b@example.com", nickname="bravo")
        cls.member = create_verified_user(email="c@example.com", nickname="charlie")
        cls.applicant = create_verified_user(email="d@example.com", nickname="delta")
        cls.outsider = create_verified_user(email="e@example.com", nickname="echo")

    def setUp(self):
        self.crew = create_crew(self.owner, join_type="approval", max_members=4)
        add_member(self.crew, self.staff, role="staff")
        add_member(self.crew, self.member)
        add_member(self.crew, self.applicant, status="pending")

    def members_url(self):
        return reverse("v1:crews:crew-members", args=[self.crew.id])

    def member_url(self, user):
        return reverse("v1:crews:crew-member-detail", args=[self.crew.id, user.id])

    def in_chat(self, user) -> bool:
        return ChatRoomMember.objects.filter(
            room=self.crew.chat_room, user=user
        ).exists()

    def last_system_message(self) -> str:
        return (
            Message.objects.filter(room=self.crew.chat_room).order_by("-id")[0].content
        )


class CrewMemberListTests(CrewMemberBase):
    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.members_url()).status_code, 401)

    def test_active_members_visible_to_anyone_in_join_order(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.members_url())
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual(
            [(m["user"]["nickname"], m["role"]) for m in results],
            [("alpha", "owner"), ("bravo", "staff"), ("charlie", "member")],
        )
        self.assertTrue(all(m["status"] == "active" for m in results))
        self.assertIn("image", results[0]["user"])

    def test_pending_members_visible_to_managers_only(self):
        for user in (self.member, self.outsider):
            self.client.force_authenticate(user)
            response = self.client.get(self.members_url(), {"status": "pending"})
            self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.staff)
        response = self.client.get(self.members_url(), {"status": "pending"})
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual([m["user"]["nickname"] for m in results], ["delta"])
        self.assertIsNone(results[0]["joined_at"])

        self.assertEqual(
            self.client.get(self.members_url(), {"status": "x"}).status_code, 400
        )


class CrewMemberApprovalTests(CrewMemberBase):
    def test_requires_auth(self):
        self.client.force_authenticate(None)
        response = self.client.patch(
            self.member_url(self.applicant), {"status": "active"}
        )
        self.assertEqual(response.status_code, 401)

    def test_member_and_outsider_cannot_approve(self):
        for user in (self.member, self.outsider):
            self.client.force_authenticate(user)
            response = self.client.patch(
                self.member_url(self.applicant), {"status": "active"}
            )
            self.assertEqual(response.status_code, 403)
        self.assertEqual(
            CrewMember.objects.get(crew=self.crew, user=self.applicant).status,
            "pending",
        )

    def test_staff_approves_and_applicant_enters_chat_room(self):
        self.client.force_authenticate(self.staff)
        response = self.client.patch(
            self.member_url(self.applicant), {"status": "active"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["user"]["nickname"], "delta")
        self.assertIsNotNone(data["joined_at"])
        self.assertTrue(self.in_chat(self.applicant))
        self.assertEqual(self.last_system_message(), "delta님이 가입했습니다")

    def test_reject_soft_deletes_request(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            self.member_url(self.applicant), {"status": "rejected"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CrewMember.objects.filter(crew=self.crew, user=self.applicant).exists()
        )
        self.assertFalse(self.in_chat(self.applicant))
        # 거절된 뒤 다시 신청할 수 있다
        self.client.force_authenticate(self.applicant)
        response = self.client.post(reverse("v1:crews:crew-join", args=[self.crew.id]))
        self.assertEqual(response.status_code, 201)

    def test_approve_respects_capacity(self):
        add_member(self.crew, self.outsider)  # 활동 4명 = max_members
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            self.member_url(self.applicant), {"status": "active"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "crew_full")

    def test_approve_unknown_request_is_404(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.member_url(self.member), {"status": "active"})
        self.assertEqual(response.status_code, 404)

    def test_requires_exactly_one_of_status_or_role(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.patch(self.member_url(self.applicant), {}).status_code, 400
        )
        response = self.client.patch(
            self.member_url(self.applicant), {"status": "active", "role": "staff"}
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            self.member_url(self.applicant), {"status": "banana"}
        )
        self.assertEqual(response.status_code, 400)


class CrewMemberRoleTests(CrewMemberBase):
    def test_owner_promotes_and_demotes(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.member_url(self.member), {"role": "staff"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["role"], "staff")

        response = self.client.patch(self.member_url(self.staff), {"role": "member"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            CrewMember.objects.get(crew=self.crew, user=self.staff).role, "member"
        )

    def test_staff_cannot_change_roles(self):
        self.client.force_authenticate(self.staff)
        response = self.client.patch(self.member_url(self.member), {"role": "staff"})
        self.assertEqual(response.status_code, 403)

    def test_owner_role_cannot_be_changed(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.member_url(self.owner), {"role": "member"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "cannot_change_owner")

    def test_role_change_requires_active_member(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.member_url(self.applicant), {"role": "staff"})
        self.assertEqual(response.status_code, 404)


class CrewMemberKickTests(CrewMemberBase):
    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.delete(self.member_url(self.member)).status_code, 401
        )

    def test_member_and_outsider_cannot_kick(self):
        for user in (self.member, self.outsider):
            self.client.force_authenticate(user)
            self.assertEqual(
                self.client.delete(self.member_url(self.staff)).status_code, 403
            )

    def test_staff_kicks_member_but_not_staff_or_owner(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.delete(self.member_url(self.owner)).status_code, 403
        )

        other_staff = create_verified_user(email="f@example.com", nickname="foxtrot")
        add_member(self.crew, other_staff, role="staff")
        self.assertEqual(
            self.client.delete(self.member_url(other_staff)).status_code, 403
        )

        self.member.profile.main_crew = self.crew
        self.member.profile.save(update_fields=["main_crew", "updated_at"])
        response = self.client.delete(self.member_url(self.member))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            CrewMember.objects.filter(crew=self.crew, user=self.member).exists()
        )
        self.assertFalse(self.in_chat(self.member))
        self.assertEqual(self.last_system_message(), "charlie님이 내보내졌습니다")
        self.member.profile.refresh_from_db()
        self.assertIsNone(self.member.profile.main_crew_id)

    def test_owner_kicks_staff_and_cannot_kick_self(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.delete(self.member_url(self.owner)).status_code, 403
        )
        self.assertEqual(
            self.client.delete(self.member_url(self.staff)).status_code, 204
        )
        self.assertFalse(self.in_chat(self.staff))

    def test_kick_pending_removes_request_without_chat_message(self):
        self.client.force_authenticate(self.owner)
        before = Message.objects.filter(room=self.crew.chat_room).count()
        self.assertEqual(
            self.client.delete(self.member_url(self.applicant)).status_code, 204
        )
        self.assertFalse(
            CrewMember.objects.filter(crew=self.crew, user=self.applicant).exists()
        )
        self.assertEqual(
            Message.objects.filter(room=self.crew.chat_room).count(), before
        )

    def test_kick_unknown_is_404(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.delete(self.member_url(self.outsider)).status_code, 404
        )
