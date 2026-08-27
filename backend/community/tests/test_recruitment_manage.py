"""모집 관리 — 참여자 목록 가시성, 승인/거절(작성자만, 정원·자동 마감), 수동 마감 훅."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from community.models import Participation, Recruitment
from community.services import close_recruitment, on_recruitment_closed
from community.tests.helpers import add_participant, create_gym, create_recruit_post


def record_hook(calls: list):
    """on_recruitment_closed 를 실제로 실행하면서 반환값을 calls 에 모은다."""

    def side_effect(recruitment):
        payload = on_recruitment_closed(recruitment)
        calls.append(payload)
        return payload

    return side_effect


class ParticipantListTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.third = create_verified_user(email="c@example.com", nickname="charlie")
        cls.gym = create_gym()

    def setUp(self):
        self.post = create_recruit_post(
            self.author, self.gym, capacity=5, join_type="approval"
        )
        add_participant(self.post, self.user, status="approved")
        add_participant(self.post, self.third, status="pending")
        self.url = reverse("v1:community:recruitment-participants", args=[self.post.id])

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_author_sees_all_statuses_in_join_order(self):
        self.client.force_authenticate(self.author)
        results = self.client.get(self.url).json()["data"]["results"]
        self.assertEqual(
            [(r["user"]["nickname"], r["status"]) for r in results],
            [("bravo", "approved"), ("charlie", "pending")],
        )

    def test_others_see_approved_only(self):
        self.client.force_authenticate(self.third)
        results = self.client.get(self.url).json()["data"]["results"]
        self.assertEqual([r["user"]["nickname"] for r in results], ["bravo"])


class ParticipantUpdateTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.third = create_verified_user(email="c@example.com", nickname="charlie")
        cls.gym = create_gym()

    def setUp(self):
        self.post = create_recruit_post(
            self.author, self.gym, capacity=3, join_type="approval"
        )
        self.participation = add_participant(self.post, self.user, status="pending")
        self.client.force_authenticate(self.author)

    def url(self, user):
        return reverse(
            "v1:community:recruitment-participant-detail",
            args=[self.post.id, user.id],
        )

    def test_only_author_can_update(self):
        self.client.force_authenticate(self.third)
        response = self.client.patch(self.url(self.user), {"status": "approved"})
        self.assertEqual(response.status_code, 403)
        self.participation.refresh_from_db()
        self.assertEqual(self.participation.status, "pending")

    def test_approve_and_reject(self):
        response = self.client.patch(self.url(self.user), {"status": "approved"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "approved")
        self.assertEqual(response.json()["data"]["user"]["nickname"], "bravo")

        response = self.client.patch(self.url(self.user), {"status": "rejected"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "rejected")

        response = self.client.patch(self.url(self.user), {"status": "pending"})
        self.assertEqual(response.status_code, 400)

    def test_unknown_participant_404(self):
        response = self.client.patch(self.url(self.third), {"status": "approved"})
        self.assertEqual(response.status_code, 404)

    def test_approval_reaching_capacity_auto_closes(self):
        add_participant(self.post, self.third, status="pending")
        self.client.patch(self.url(self.user), {"status": "approved"})
        self.post.recruitment.refresh_from_db()
        self.assertEqual(self.post.recruitment.status, Recruitment.Status.OPEN)

        calls = []
        with patch(
            "community.services.on_recruitment_closed", side_effect=record_hook(calls)
        ):
            response = self.client.patch(self.url(self.third), {"status": "approved"})
        self.assertEqual(response.status_code, 200)
        self.post.recruitment.refresh_from_db()
        self.assertEqual(self.post.recruitment.status, Recruitment.Status.CLOSED)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["member_user_ids"], [self.author.id, self.user.id, self.third.id]
        )

    def test_approve_when_closed_rejected(self):
        self.post.recruitment.status = Recruitment.Status.CLOSED
        self.post.recruitment.save()
        response = self.client.patch(self.url(self.user), {"status": "approved"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "recruitment_closed")


class RecruitmentCloseTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.third = create_verified_user(email="c@example.com", nickname="charlie")
        cls.gym = create_gym()

    def setUp(self):
        self.post = create_recruit_post(self.author, self.gym, capacity=5)
        add_participant(self.post, self.user, status="approved")
        add_participant(self.post, self.third, status="rejected")
        self.url = reverse("v1:community:recruitment-close", args=[self.post.id])

    def test_only_author_can_close(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.post.recruitment.refresh_from_db()
        self.assertEqual(self.post.recruitment.status, Recruitment.Status.OPEN)

    def test_author_close_calls_hook_with_approved_members(self):
        self.client.force_authenticate(self.author)
        calls = []
        with patch(
            "community.services.on_recruitment_closed", side_effect=record_hook(calls)
        ):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "closed")
        self.assertEqual(response.json()["data"]["approved_count"], 1)

        self.assertEqual(len(calls), 1)
        payload = calls[0]
        self.assertEqual(payload["recruitment_id"], self.post.recruitment.id)
        self.assertEqual(payload["author_id"], self.author.id)
        # rejected 는 제외, 작성자가 맨 앞
        self.assertEqual(payload["member_user_ids"], [self.author.id, self.user.id])

        # 두 번 마감은 400
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "recruitment_closed")

    def test_service_close_updates_caller_instance(self):
        rec = self.post.recruitment
        close_recruitment(rec)
        self.assertEqual(rec.status, Recruitment.Status.CLOSED)
        self.assertEqual(
            Participation.objects.filter(recruitment=rec, status="approved").count(), 1
        )
