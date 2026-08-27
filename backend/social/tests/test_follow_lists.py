from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from social.models import Follow


class FollowListTests(APITestCase):
    def setUp(self):
        self.me = create_verified_user(email="me@example.com", nickname="me")
        self.target = create_verified_user(email="t@example.com", nickname="target")
        self.fan1 = create_verified_user(email="f1@example.com", nickname="fan1")
        self.fan2 = create_verified_user(email="f2@example.com", nickname="fan2")
        self.fan1.profile.image = "https://cdn.example.com/fan1.png"
        self.fan1.profile.save(update_fields=["image", "updated_at"])

        Follow.objects.create(follower=self.fan1, following=self.target)
        Follow.objects.create(follower=self.fan2, following=self.target)
        Follow.objects.create(follower=self.target, following=self.fan1)
        # 요청자(me)는 fan1 만 팔로우 중
        Follow.objects.create(follower=self.me, following=self.fan1)
        self.client.force_authenticate(self.me)

    def followers_url(self, user_id):
        return reverse("v1:social:followers", kwargs={"pk": user_id})

    def following_url(self, user_id):
        return reverse("v1:social:following", kwargs={"pk": user_id})

    def test_followers_list_with_is_following(self):
        response = self.client.get(self.followers_url(self.target.pk))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("next_cursor", data)
        results = data["results"]
        # 최근 팔로우 순
        self.assertEqual([r["nickname"] for r in results], ["fan2", "fan1"])
        by_name = {r["nickname"]: r for r in results}
        self.assertEqual(
            set(by_name["fan1"]), {"id", "nickname", "image", "is_following"}
        )
        self.assertTrue(by_name["fan1"]["is_following"])
        self.assertFalse(by_name["fan2"]["is_following"])
        self.assertEqual(by_name["fan1"]["image"], "https://cdn.example.com/fan1.png")
        self.assertIsNone(by_name["fan2"]["image"])

    def test_following_list(self):
        response = self.client.get(self.following_url(self.target.pk))
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual([r["nickname"] for r in results], ["fan1"])
        self.assertTrue(results[0]["is_following"])

    def test_cursor_pagination_with_limit(self):
        response = self.client.get(self.followers_url(self.target.pk), {"limit": 1})
        data = response.json()["data"]
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["nickname"], "fan2")
        self.assertIsNotNone(data["next_cursor"])

        response = self.client.get(data["next_cursor"])
        data = response.json()["data"]
        self.assertEqual(data["results"][0]["nickname"], "fan1")
        self.assertIsNone(data["next_cursor"])

    def test_excludes_soft_deleted_users(self):
        self.fan2.delete()
        results = self.client.get(self.followers_url(self.target.pk)).json()["data"][
            "results"
        ]
        self.assertEqual([r["nickname"] for r in results], ["fan1"])

    def test_empty_list(self):
        # me 는 아무도 팔로우하지 않았고(fan1 제외) 팔로워도 없다.
        results = self.client.get(self.followers_url(self.me.pk)).json()["data"][
            "results"
        ]
        self.assertEqual(results, [])

    def test_unknown_user_404(self):
        self.assertEqual(self.client.get(self.followers_url(99999)).status_code, 404)
        self.assertEqual(self.client.get(self.following_url(99999)).status_code, 404)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(self.followers_url(self.target.pk)).status_code, 401
        )
        self.assertEqual(
            self.client.get(self.following_url(self.target.pk)).status_code, 401
        )
