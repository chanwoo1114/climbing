from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.services import register_user
from gyms.models import Gym


class GymReviewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gym = Gym.objects.create(
            name="리뷰암장", address="서울", location=Point(127.0, 37.5, srid=4326)
        )
        cls.user = register_user(
            email="rev@example.com", nickname="rev", password="s3cure-pass!"
        )
        cls.url = reverse("v1:gyms:reviews", args=[cls.gym.id])

    def test_create_requires_auth(self):
        response = self.client.post(self.url, {"rating": 5, "content": "좋아요"})
        self.assertEqual(response.status_code, 401)

    def test_create_and_list(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"rating": 4, "content": "홀드 다양함"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["user"]["nickname"], "rev")

        self.client.force_authenticate(None)  # 목록은 공개
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual(results[0]["content"], "홀드 다양함")

    def test_rating_out_of_range_fails(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"rating": 6, "content": "x"})
        self.assertEqual(response.status_code, 400)
