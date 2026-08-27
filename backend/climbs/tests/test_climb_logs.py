"""등반 기록 CRUD — 작성 검증, 내 목록/필터, 상세 공개 범위, 수정·삭제 권한."""

import datetime

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.models import ClimbLog
from climbs.tests.helpers import create_difficulty, create_gym, create_log


class ClimbLogCreateTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_verified_user(email="a@example.com", nickname="alpha")
        cls.gym = create_gym()
        cls.other_gym = create_gym(name="다른암장")
        cls.difficulty = create_difficulty(cls.gym)
        cls.other_difficulty = create_difficulty(cls.other_gym, name="빨강")
        cls.url = reverse("v1:climbs:log-list")

    def setUp(self):
        self.client.force_authenticate(self.user)

    def payload(self, **overrides):
        data = {
            "gym": self.gym.id,
            "difficulty": self.difficulty.id,
            "is_success": True,
            "attempts": 3,
            "memo": "오늘 완등",
            "climbed_at": "2026-08-20",
        }
        data.update(overrides)
        return data

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, 401)

    def test_create_returns_card_shape(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["user"]["nickname"], "alpha")
        self.assertIsNone(data["user"]["image"])
        self.assertEqual(data["gym"], {"id": self.gym.id, "name": "테스트암장"})
        self.assertEqual(data["difficulty"]["color"], "#5f7d4e")
        self.assertEqual(data["attempts"], 3)
        self.assertEqual(data["climbed_at"], "2026-08-20")
        self.assertTrue(data["is_shared"])
        self.assertEqual(data["like_count"], 0)
        self.assertEqual(data["comment_count"], 0)
        self.assertFalse(data["is_liked"])
        self.assertEqual(ClimbLog.objects.get(pk=data["id"]).user, self.user)

    def test_defaults(self):
        response = self.client.post(
            self.url, {"gym": self.gym.id, "is_success": False}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["attempts"], 1)
        self.assertIsNone(data["difficulty"])
        self.assertEqual(data["climbed_at"], datetime.date.today().isoformat())

    def test_difficulty_must_belong_to_gym(self):
        response = self.client.post(
            self.url, self.payload(difficulty=self.other_difficulty.id), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("difficulty", response.json()["error"]["fields"])

    def test_attempts_must_be_positive(self):
        response = self.client.post(self.url, self.payload(attempts=0), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("attempts", response.json()["error"]["fields"])

    def test_future_date_rejected(self):
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        response = self.client.post(
            self.url, self.payload(climbed_at=tomorrow.isoformat()), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("climbed_at", response.json()["error"]["fields"])

    def test_memo_too_long_rejected(self):
        response = self.client.post(
            self.url, self.payload(memo="가" * 1001), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("memo", response.json()["error"]["fields"])


class ClimbLogListTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_verified_user(email="a@example.com", nickname="alpha")
        cls.other = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.gym2 = create_gym(name="둘째암장")
        cls.mine_success = create_log(cls.user, cls.gym, is_success=True)
        cls.mine_fail = create_log(cls.user, cls.gym2, is_success=False)
        cls.mine_private = create_log(cls.user, cls.gym, is_shared=False)
        create_log(cls.other, cls.gym)
        cls.url = reverse("v1:climbs:log-list")

    def setUp(self):
        self.client.force_authenticate(self.user)

    def ids(self, response):
        return [item["id"] for item in response.json()["data"]["results"]]

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_lists_only_my_logs_newest_first(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.ids(response),
            [self.mine_private.id, self.mine_fail.id, self.mine_success.id],
        )
        self.assertIn("next_cursor", response.json()["data"])

    def test_filter_by_gym_and_success(self):
        response = self.client.get(self.url, {"gym": self.gym2.id})
        self.assertEqual(self.ids(response), [self.mine_fail.id])

        response = self.client.get(self.url, {"is_success": "true"})
        self.assertEqual(
            self.ids(response), [self.mine_private.id, self.mine_success.id]
        )

    def test_cursor_pagination(self):
        response = self.client.get(self.url, {"limit": 2})
        data = response.json()["data"]
        self.assertEqual(len(data["results"]), 2)
        self.assertIsNotNone(data["next_cursor"])

    def test_excludes_soft_deleted(self):
        self.mine_fail.delete()
        response = self.client.get(self.url)
        self.assertNotIn(self.mine_fail.id, self.ids(response))


class ClimbLogDetailTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.other = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.difficulty = create_difficulty(cls.gym)
        cls.shared = create_log(cls.owner, cls.gym, is_shared=True)
        cls.private = create_log(cls.owner, cls.gym, is_shared=False)

    @staticmethod
    def url(log):
        return reverse("v1:climbs:log-detail", args=[log.id])

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url(self.shared)).status_code, 401)

    def test_owner_sees_private(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url(self.private))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], self.private.id)

    def test_other_sees_shared_but_not_private(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url(self.shared)).status_code, 200)
        self.assertEqual(self.client.get(self.url(self.private)).status_code, 404)

    def test_owner_can_patch(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            self.url(self.shared),
            {"memo": "수정", "difficulty": self.difficulty.id, "is_shared": False},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["memo"], "수정")
        self.assertEqual(data["difficulty"]["id"], self.difficulty.id)
        self.assertFalse(data["is_shared"])

    def test_patch_difficulty_from_other_gym_rejected(self):
        other_gym = create_gym(name="다른암장")
        bad = create_difficulty(other_gym, name="빨강")
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.url(self.shared), {"difficulty": bad.id})
        self.assertEqual(response.status_code, 400)

    def test_other_cannot_patch_or_delete(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.patch(self.url(self.shared), {"memo": "x"}).status_code, 403
        )
        self.assertEqual(self.client.delete(self.url(self.shared)).status_code, 403)
        self.assertTrue(ClimbLog.objects.filter(pk=self.shared.id).exists())

    def test_owner_delete_is_soft(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(self.url(self.shared))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ClimbLog.objects.filter(pk=self.shared.id).exists())
        deleted = ClimbLog.all_objects.get(pk=self.shared.id)
        self.assertTrue(deleted.is_deleted)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(self.client.get(self.url(self.shared)).status_code, 404)
