"""모집 참여 — 선착순/승인제, 정원 초과(recruitment_full), 자동 마감, 취소·재참여."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from community.models import Participation, Recruitment
from community.services import join_recruitment
from community.tests.helpers import (
    add_participant,
    create_gym,
    create_post,
    create_recruit_post,
)


class RecruitmentJoinTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.third = create_verified_user(email="c@example.com", nickname="charlie")
        cls.fourth = create_verified_user(email="d@example.com", nickname="delta")
        cls.gym = create_gym()

    def setUp(self):
        self.client.force_authenticate(self.user)

    @staticmethod
    def join_url(post):
        return reverse("v1:community:recruitment-join", args=[post.id])

    @staticmethod
    def cancel_url(post):
        return reverse("v1:community:recruitment-cancel", args=[post.id])

    @staticmethod
    def detail_url(post):
        return reverse("v1:community:post-detail", args=[post.id])

    def test_requires_auth(self):
        post = create_recruit_post(self.author, self.gym)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.join_url(post)).status_code, 401)
        self.assertEqual(self.client.delete(self.cancel_url(post)).status_code, 401)

    def test_instant_join_is_approved_immediately(self):
        post = create_recruit_post(self.author, self.gym, capacity=3)
        response = self.client.post(self.join_url(post))
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["status"], "approved")
        self.assertEqual(data["user"]["nickname"], "bravo")

        rec = self.client.get(self.detail_url(post)).json()["data"]["recruitment"]
        self.assertEqual(rec["approved_count"], 1)
        self.assertEqual(rec["my_participation_status"], "approved")
        self.assertEqual(rec["status"], "open")

    def test_approval_join_is_pending(self):
        post = create_recruit_post(self.author, self.gym, join_type="approval")
        response = self.client.post(self.join_url(post))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["status"], "pending")

        rec = self.client.get(self.detail_url(post)).json()["data"]["recruitment"]
        self.assertEqual(rec["approved_count"], 0)
        self.assertEqual(rec["my_participation_status"], "pending")

    def test_author_cannot_join_own(self):
        post = create_recruit_post(self.author, self.gym)
        self.client.force_authenticate(self.author)
        response = self.client.post(self.join_url(post))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "own_recruitment")

    def test_duplicate_join_rejected(self):
        post = create_recruit_post(self.author, self.gym, capacity=5)
        self.client.post(self.join_url(post))
        response = self.client.post(self.join_url(post))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "already_joined")
        self.assertEqual(Participation.objects.filter(user=self.user).count(), 1)

    def test_free_post_has_no_recruitment(self):
        post = create_post(self.author)
        self.assertEqual(self.client.post(self.join_url(post)).status_code, 404)

    def test_capacity_reached_closes_and_next_join_is_full(self):
        """정원 3(작성자 포함) → 2명 참여로 가득 차 자동 마감, 3번째는 recruitment_full."""
        post = create_recruit_post(self.author, self.gym, capacity=3)
        self.assertEqual(self.client.post(self.join_url(post)).status_code, 201)

        self.client.force_authenticate(self.third)
        self.assertEqual(self.client.post(self.join_url(post)).status_code, 201)
        post.recruitment.refresh_from_db()
        self.assertEqual(post.recruitment.status, Recruitment.Status.CLOSED)

        self.client.force_authenticate(self.fourth)
        response = self.client.post(self.join_url(post))
        self.assertEqual(response.status_code, 400)
        # 자동 마감된 상태라 closed 로 걸린다
        self.assertEqual(response.json()["error"]["code"], "recruitment_closed")
        self.assertEqual(
            Participation.objects.filter(recruitment=post.recruitment).count(), 2
        )

    def test_full_but_still_open_returns_recruitment_full(self):
        """상태가 open 인데 승인 인원이 이미 정원인 경우(경합 등) → recruitment_full."""
        post = create_recruit_post(self.author, self.gym, capacity=3)
        add_participant(post, self.third)
        add_participant(post, self.fourth)
        # status 는 여전히 open (직접 만든 참여라 자동 마감이 안 돌았음)
        response = self.client.post(self.join_url(post))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "recruitment_full")
        self.assertFalse(
            Participation.objects.filter(
                recruitment=post.recruitment, user=self.user
            ).exists()
        )

    def test_service_never_exceeds_capacity(self):
        """서비스 레벨에서 정원까지 채운 뒤 한 명 더 → RecruitmentFull (행 잠금 구간)."""
        from community.exceptions import RecruitmentClosed, RecruitmentFull

        post = create_recruit_post(self.author, self.gym, capacity=3)
        rec = post.recruitment
        join_recruitment(rec, self.user)
        join_recruitment(rec, self.third)
        with self.assertRaises((RecruitmentFull, RecruitmentClosed)):
            join_recruitment(rec, self.fourth)
        approved = Participation.objects.filter(
            recruitment=rec, status=Participation.Status.APPROVED
        ).count()
        self.assertEqual(approved + 1, rec.capacity)

    def test_join_closed_recruitment(self):
        post = create_recruit_post(self.author, self.gym, capacity=5)
        post.recruitment.status = Recruitment.Status.CLOSED
        post.recruitment.save()
        response = self.client.post(self.join_url(post))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "recruitment_closed")

    def test_cancel_then_rejoin(self):
        post = create_recruit_post(self.author, self.gym, capacity=5)
        self.client.post(self.join_url(post))
        self.assertEqual(self.client.delete(self.cancel_url(post)).status_code, 204)

        rec = post.recruitment
        self.assertFalse(Participation.objects.filter(recruitment=rec).exists())
        canceled = Participation.all_objects.get(recruitment=rec, user=self.user)
        self.assertTrue(canceled.is_deleted)
        self.assertEqual(canceled.status, Participation.Status.CANCELED)

        detail = self.client.get(self.detail_url(post)).json()["data"]["recruitment"]
        self.assertEqual(detail["approved_count"], 0)
        self.assertIsNone(detail["my_participation_status"])

        # 재참여 — UNIQUE 충돌 없이 새 행
        self.assertEqual(self.client.post(self.join_url(post)).status_code, 201)
        self.assertEqual(Participation.all_objects.filter(recruitment=rec).count(), 2)

    def test_cancel_without_participation_404(self):
        post = create_recruit_post(self.author, self.gym)
        response = self.client.delete(self.cancel_url(post))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_participating")

    def test_cancel_after_close_rejected(self):
        post = create_recruit_post(self.author, self.gym, capacity=5)
        self.client.post(self.join_url(post))
        post.recruitment.status = Recruitment.Status.CLOSED
        post.recruitment.save()
        response = self.client.delete(self.cancel_url(post))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "recruitment_closed")
