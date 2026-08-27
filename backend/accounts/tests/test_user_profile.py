from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.tests.helpers import create_verified_user
from gyms.models import Gym
from social.models import Follow


class PublicProfileTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gym = Gym.objects.create(
            name="홈짐", address="서울", location=Point(127.0, 37.5, srid=4326)
        )

    def setUp(self):
        self.me = create_verified_user(email="me@example.com", nickname="me")
        self.other = create_verified_user(email="other@example.com", nickname="other")
        self.third = create_verified_user(email="third@example.com", nickname="third")
        self.other.profile.bio = "볼더링"
        self.other.profile.image = "https://cdn.example.com/other.png"
        self.other.profile.home_gym = self.gym
        self.other.profile.save(
            update_fields=["bio", "image", "home_gym", "updated_at"]
        )
        self.client.force_authenticate(self.me)

    def url(self, user_id):
        return reverse("v1:accounts:detail", kwargs={"pk": user_id})

    def test_profile_fields(self):
        Follow.objects.create(follower=self.me, following=self.other)
        Follow.objects.create(follower=self.third, following=self.other)
        Follow.objects.create(follower=self.other, following=self.third)

        response = self.client.get(self.url(self.other.pk))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["id"], self.other.pk)
        self.assertEqual(data["nickname"], "other")
        self.assertEqual(data["bio"], "볼더링")
        self.assertEqual(data["image"], "https://cdn.example.com/other.png")
        self.assertEqual(data["home_gym"], {"id": self.gym.id, "name": "홈짐"})
        self.assertEqual(data["follower_count"], 2)
        self.assertEqual(data["following_count"], 1)
        self.assertTrue(data["is_following"])
        self.assertFalse(data["is_me"])
        self.assertIn("created_at", data)
        self.assertNotIn("email", data)

    def test_counts_exclude_soft_deleted_followers(self):
        Follow.objects.create(follower=self.third, following=self.other)
        Follow.objects.create(follower=self.other, following=self.third)
        self.third.delete()
        data = self.client.get(self.url(self.other.pk)).json()["data"]
        self.assertEqual(data["follower_count"], 0)
        self.assertEqual(data["following_count"], 0)

    def test_own_profile_is_me(self):
        data = self.client.get(self.url(self.me.pk)).json()["data"]
        self.assertTrue(data["is_me"])
        self.assertFalse(data["is_following"])
        self.assertIsNone(data["home_gym"])
        self.assertIsNone(data["image"])
        self.assertEqual(data["follower_count"], 0)

    def test_profile_without_userprofile_row(self):
        admin = User.objects.create_user(
            email="admin@example.com", nickname="admin", password="s3cure-pass!"
        )
        response = self.client.get(self.url(admin.pk))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["bio"], "")
        self.assertIsNone(data["image"])
        self.assertIsNone(data["home_gym"])

    def test_soft_deleted_user_404(self):
        self.other.delete()
        self.assertEqual(self.client.get(self.url(self.other.pk)).status_code, 404)

    def test_unknown_user_404(self):
        self.assertEqual(self.client.get(self.url(99999)).status_code, 404)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url(self.other.pk)).status_code, 401)
