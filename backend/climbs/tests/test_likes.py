"""좋아요 — 멱등 POST/DELETE, 카운트·is_liked 반영, 비공개 기록 접근 차단."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.models import ClimbLogLike
from climbs.tests.helpers import create_gym, create_log


class ClimbLogLikeTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym)
        cls.private = create_log(cls.owner, cls.gym, is_shared=False)
        cls.url = reverse("v1:climbs:log-like", args=[cls.log.id])
        cls.detail_url = reverse("v1:climbs:log-detail", args=[cls.log.id])

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.url).status_code, 401)

    def test_like_is_idempotent(self):
        self.assertEqual(self.client.post(self.url).status_code, 204)
        self.assertEqual(self.client.post(self.url).status_code, 204)
        self.assertEqual(ClimbLogLike.objects.filter(climb_log=self.log).count(), 1)

        data = self.client.get(self.detail_url).json()["data"]
        self.assertEqual(data["like_count"], 1)
        self.assertTrue(data["is_liked"])

    def test_unlike_then_relike(self):
        self.client.post(self.url)
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertEqual(ClimbLogLike.objects.filter(climb_log=self.log).count(), 0)
        self.assertEqual(ClimbLogLike.all_objects.filter(climb_log=self.log).count(), 1)

        data = self.client.get(self.detail_url).json()["data"]
        self.assertEqual(data["like_count"], 0)
        self.assertFalse(data["is_liked"])

        # 취소했던 좋아요를 다시 누르면 복구 (UNIQUE 충돌 없이)
        self.assertEqual(self.client.post(self.url).status_code, 204)
        self.assertEqual(ClimbLogLike.objects.filter(climb_log=self.log).count(), 1)
        self.assertEqual(ClimbLogLike.all_objects.filter(climb_log=self.log).count(), 1)

    def test_unlike_without_like_is_ok(self):
        self.assertEqual(self.client.delete(self.url).status_code, 204)

    def test_is_liked_is_per_requester(self):
        self.client.post(self.url)
        self.client.force_authenticate(self.owner)
        data = self.client.get(self.detail_url).json()["data"]
        self.assertEqual(data["like_count"], 1)
        self.assertFalse(data["is_liked"])

    def test_cannot_like_private_log_of_other(self):
        url = reverse("v1:climbs:log-like", args=[self.private.id])
        self.assertEqual(self.client.post(url).status_code, 404)
