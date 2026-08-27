from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from social.models import Follow


class UserSearchTests(APITestCase):
    url = reverse("v1:accounts:search")

    def setUp(self):
        self.me = create_verified_user(email="me@example.com", nickname="climber_me")
        self.casey = create_verified_user(email="c@example.com", nickname="Casey")
        self.casual = create_verified_user(email="ca@example.com", nickname="casual")
        self.bob = create_verified_user(email="b@example.com", nickname="bob")
        self.client.force_authenticate(self.me)

    def test_search_icontains_case_insensitive(self):
        response = self.client.get(self.url, {"q": "cas"})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("next_cursor", data)
        self.assertEqual({r["nickname"] for r in data["results"]}, {"Casey", "casual"})
        self.assertEqual(
            set(data["results"][0]), {"id", "nickname", "image", "is_following"}
        )

    def test_search_marks_is_following(self):
        Follow.objects.create(follower=self.me, following=self.casey)
        results = self.client.get(self.url, {"q": "cas"}).json()["data"]["results"]
        by_name = {r["nickname"]: r["is_following"] for r in results}
        self.assertTrue(by_name["Casey"])
        self.assertFalse(by_name["casual"])

    def test_search_excludes_soft_deleted(self):
        self.casey.delete()
        results = self.client.get(self.url, {"q": "cas"}).json()["data"]["results"]
        self.assertEqual([r["nickname"] for r in results], ["casual"])

    def test_search_no_match_is_empty(self):
        results = self.client.get(self.url, {"q": "zzz"}).json()["data"]["results"]
        self.assertEqual(results, [])

    def test_search_requires_query(self):
        for params in ({}, {"q": ""}, {"q": "   "}):
            response = self.client.get(self.url, params)
            self.assertEqual(response.status_code, 400, params)
            self.assertIn("q", response.json()["error"]["fields"])

    def test_limit_capped_at_20(self):
        for i in range(25):
            create_verified_user(email=f"u{i}@example.com", nickname=f"user{i:02d}")
        response = self.client.get(self.url, {"q": "user", "limit": 100})
        data = response.json()["data"]
        self.assertEqual(len(data["results"]), 20)
        self.assertIsNotNone(data["next_cursor"])

        response = self.client.get(data["next_cursor"])
        self.assertEqual(len(response.json()["data"]["results"]), 5)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url, {"q": "cas"}).status_code, 401)
