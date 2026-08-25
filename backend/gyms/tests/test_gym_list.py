from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from gyms.models import Gym


class GymListTests(APITestCase):
    url = reverse("v1:gyms:list")

    @classmethod
    def setUpTestData(cls):
        # 서울시청 / 강남역 / 부산역 — 뷰포트·거리 검증용 좌표
        cls.city_hall = Gym.objects.create(
            name="시청암장",
            address="서울",
            location=Point(126.9779, 37.5663, srid=4326),
        )
        cls.gangnam = Gym.objects.create(
            name="강남암장",
            address="서울",
            location=Point(127.0276, 37.4979, srid=4326),
        )
        cls.busan = Gym.objects.create(
            name="부산암장",
            address="부산",
            location=Point(129.0403, 35.1151, srid=4326),
        )

    def test_list_is_public(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 3)

    def test_bbox_filters_viewport(self):
        # 서울만 포함하는 bbox
        response = self.client.get(self.url, {"bbox": "126.7,37.4,127.2,37.7"})
        names = {g["name"] for g in response.json()["data"]}
        self.assertEqual(names, {"시청암장", "강남암장"})

    def test_invalid_bbox_returns_400(self):
        response = self.client.get(self.url, {"bbox": "oops"})
        self.assertEqual(response.status_code, 400)

    def test_distance_ordering(self):
        # 시청 좌표 기준 → 시청암장이 가장 가깝다
        response = self.client.get(self.url, {"lat": "37.5663", "lng": "126.9779"})
        data = response.json()["data"]
        self.assertEqual(data[0]["name"], "시청암장")
        self.assertIsNotNone(data[0]["distance_m"])
        self.assertEqual(data[-1]["name"], "부산암장")

    def test_radius_filter(self):
        # 시청 기준 반경 20km — 부산 제외
        response = self.client.get(
            self.url, {"lat": "37.5663", "lng": "126.9779", "radius": "20000"}
        )
        names = {g["name"] for g in response.json()["data"]}
        self.assertEqual(names, {"시청암장", "강남암장"})
