from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from gyms.models import Gym, GymDifficulty, GymPrice


class GymDetailTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gym = Gym.objects.create(
            name="테스트암장", address="서울", location=Point(127.0, 37.5, srid=4326)
        )
        GymPrice.objects.create(gym=cls.gym, name="1일권", price=25000)
        GymDifficulty.objects.create(gym=cls.gym, name="초록", color="#5f7d4e", order=0)
        GymDifficulty.objects.create(gym=cls.gym, name="빨강", color="#c04a38", order=1)

    def test_detail_includes_nested(self):
        response = self.client.get(reverse("v1:gyms:detail", args=[self.gym.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["prices"][0]["name"], "1일권")
        self.assertEqual([d["name"] for d in data["difficulties"]], ["초록", "빨강"])
        self.assertAlmostEqual(data["lat"], 37.5)

    def test_difficulty_list(self):
        response = self.client.get(reverse("v1:gyms:difficulties", args=[self.gym.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 2)

    def test_missing_gym_returns_404(self):
        response = self.client.get(reverse("v1:gyms:detail", args=[99999]))
        self.assertEqual(response.status_code, 404)


class GymDetailReviewStatsTests(APITestCase):
    def setUp(self):
        from accounts.tests.helpers import create_verified_user
        from gyms.models import GymReview

        self.gym = Gym.objects.create(
            name="통계암장", address="서울", location=Point(127.0, 37.5, srid=4326)
        )
        u1 = create_verified_user(email="a@example.com", nickname="a1")
        u2 = create_verified_user(email="b@example.com", nickname="b2")
        GymReview.objects.create(gym=self.gym, user=u1, rating=5, content="좋아요")
        GymReview.objects.create(gym=self.gym, user=u2, rating=3, content="보통")
        deleted = GymReview.objects.create(gym=self.gym, user=u2, rating=1, content="x")
        deleted.delete()  # soft delete → 집계 제외

    def test_detail_has_review_stats(self):
        data = self.client.get(reverse("v1:gyms:detail", args=[self.gym.id])).json()[
            "data"
        ]
        self.assertEqual(data["review_count"], 2)
        self.assertAlmostEqual(data["rating_avg"], 4.0)

    def test_detail_without_reviews(self):
        gym = Gym.objects.create(
            name="빈암장", address="서울", location=Point(127.0, 37.5, srid=4326)
        )
        data = self.client.get(reverse("v1:gyms:detail", args=[gym.id])).json()["data"]
        self.assertEqual(data["review_count"], 0)
        self.assertIsNone(data["rating_avg"])
