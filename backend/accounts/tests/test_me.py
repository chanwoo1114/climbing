from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User, UserProfile
from accounts.services import register_user
from gyms.models import Gym


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

    def test_me_updates_image(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            self.url, {"image": "https://cdn.example.com/me.png"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["image"], "https://cdn.example.com/me.png"
        )

    def test_me_rejects_nickname_taken_case_insensitively(self):
        register_user(
            email="other@example.com", nickname="Casey", password="s3cure-pass!"
        )
        self.client.force_authenticate(self.user)
        response = self.client.patch(self.url, {"nickname": "casey"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("nickname", response.json()["error"]["fields"])

    def test_me_keeps_own_nickname_on_update(self):
        # 자기 닉네임을 그대로 보내도 중복으로 막히면 안 된다.
        self.client.force_authenticate(self.user)
        response = self.client.patch(self.url, {"nickname": "me", "bio": "변경"})
        self.assertEqual(response.status_code, 200)


class MeHomeGymTests(APITestCase):
    url = reverse("v1:accounts:me")

    @classmethod
    def setUpTestData(cls):
        cls.gym = Gym.objects.create(
            name="테스트암장", address="서울", location=Point(127.0, 37.5, srid=4326)
        )

    def setUp(self):
        self.user = register_user(
            email="me@example.com", nickname="me", password="s3cure-pass!"
        )
        self.client.force_authenticate(self.user)

    def test_home_gym_defaults_to_null(self):
        data = self.client.get(self.url).json()["data"]
        self.assertIsNone(data["home_gym"])
        self.assertIsNone(data["home_gym_name"])

    def test_sets_and_clears_home_gym(self):
        response = self.client.patch(self.url, {"home_gym": self.gym.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["home_gym"], self.gym.id)
        self.assertEqual(data["home_gym_name"], "테스트암장")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.home_gym_id, self.gym.id)

        response = self.client.patch(self.url, {"home_gym": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["home_gym"])

    def test_rejects_unknown_gym(self):
        response = self.client.patch(self.url, {"home_gym": 99999})
        self.assertEqual(response.status_code, 400)
        self.assertIn("home_gym", response.json()["error"]["fields"])

    def test_rejects_soft_deleted_gym(self):
        self.gym.delete()  # soft delete → objects 에서 빠진다
        response = self.client.patch(self.url, {"home_gym": self.gym.id})
        self.assertEqual(response.status_code, 400)


class MeWithoutProfileTests(APITestCase):
    """createsuperuser·admin 으로 만든 계정은 UserProfile 이 없다."""

    url = reverse("v1:accounts:me")

    def setUp(self):
        self.user = User.objects.create_user(
            email="admin@example.com", nickname="admin", password="s3cure-pass!"
        )
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        self.client.force_authenticate(self.user)

    def test_get_creates_profile_instead_of_500(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["bio"], "")
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_patch_profile_field_without_profile(self):
        response = self.client.patch(self.url, {"bio": "관리자"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.profile.bio, "관리자")
