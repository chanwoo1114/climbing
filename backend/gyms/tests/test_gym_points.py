from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from gyms.models import Gym
from gyms.views import MAX_MAP_RESULTS


class GymPointsTests(APITestCase):
    url = reverse("v1:gyms:points")

    def test_returns_all_gyms_beyond_list_cap(self):
        Gym.objects.bulk_create(
            Gym(name=f"암장{i}", address="서울", location=Point(127.0, 37.5, srid=4326))
            for i in range(MAX_MAP_RESULTS + 5)
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), MAX_MAP_RESULTS + 5)
        self.assertEqual(set(data[0]), {"id", "name", "lat", "lng"})
        self.assertAlmostEqual(data[0]["lat"], 37.5)

    def test_excludes_soft_deleted(self):
        gym = Gym.objects.create(
            name="닫은암장", address="서울", location=Point(127.0, 37.5, srid=4326)
        )
        gym.delete()
        self.assertEqual(self.client.get(self.url).json()["data"], [])

    def test_public(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
