from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User, UserProfile


class RegisterTests(APITestCase):
    url = reverse("v1:auth:register")

    def test_register_creates_user_and_profile(self):
        response = self.client.post(
            self.url,
            {
                "email": "climber@example.com",
                "nickname": "chalk",
                "password": "s3cure-pass!",
            },
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["email"], "climber@example.com")
        self.assertNotIn("password", body["data"])
        user = User.objects.get(email="climber@example.com")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_duplicate_email_fails(self):
        User.objects.create_user(
            email="dup@example.com", nickname="one", password="s3cure-pass!"
        )
        response = self.client.post(
            self.url,
            {"email": "dup@example.com", "nickname": "two", "password": "s3cure-pass!"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_weak_password_fails(self):
        response = self.client.post(
            self.url,
            {"email": "weak@example.com", "nickname": "weak", "password": "1234"},
        )
        self.assertEqual(response.status_code, 400)
