from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User


class JwtLoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="login@example.com", nickname="login", password="s3cure-pass!"
        )

    def _login(self):
        return self.client.post(
            reverse("v1:auth:login"),
            {"email": "login@example.com", "password": "s3cure-pass!"},
        )

    def test_login_returns_token_pair(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("access", data)
        self.assertIn("refresh", data)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            reverse("v1:auth:login"),
            {"email": "login@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["success"])

    def test_refresh_rotates_tokens(self):
        refresh = self._login().json()["data"]["refresh"]
        response = self.client.post(reverse("v1:auth:refresh"), {"refresh": refresh})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("access", data)
        self.assertIn("refresh", data)  # ROTATE_REFRESH_TOKENS=True

    def test_logout_blacklists_refresh(self):
        tokens = self._login().json()["data"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = self.client.post(
            reverse("v1:auth:logout"), {"refresh": tokens["refresh"]}
        )
        self.assertEqual(response.status_code, 204)
        # 블랙리스트된 토큰으로는 재발급이 안 된다.
        response = self.client.post(
            reverse("v1:auth:refresh"), {"refresh": tokens["refresh"]}
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_requires_auth(self):
        response = self.client.post(reverse("v1:auth:logout"), {"refresh": "x"})
        self.assertEqual(response.status_code, 401)
