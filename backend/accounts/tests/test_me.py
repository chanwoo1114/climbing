from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.services import register_user


class MeTests(APITestCase):
    url = reverse("v1:accounts:me")

    def setUp(self):
        self.user = register_user(
            email="me@example.com", nickname="me", password="s3cure-pass!"
        )

    def test_me_requires_auth(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_me_returns_profile(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["nickname"], "me")
        self.assertIn("bio", data)

    def test_me_updates_nickname_and_bio(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            self.url, {"nickname": "new-me", "bio": "볼더링 3년차"}
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "new-me")
        self.assertEqual(self.user.profile.bio, "볼더링 3년차")
