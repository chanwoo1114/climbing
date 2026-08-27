"""대표 크루(UserProfile.main_crew) — users/me 읽기/쓰기, 공개 프로필 노출, 크루 삭제 시 해제."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from crews.tests.helpers import add_member, create_crew


class MainCrewTests(APITestCase):
    me_url = reverse("v1:accounts:me")

    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")

    def setUp(self):
        self.crew = create_crew(self.owner, name="내크루")
        add_member(self.crew, self.user)
        self.other = create_crew(self.owner, name="남의크루")
        self.client.force_authenticate(self.user)

    def profile_url(self):
        return reverse("v1:accounts:detail", args=[self.user.id])

    def test_defaults_to_null(self):
        data = self.client.get(self.me_url).json()["data"]
        self.assertIsNone(data["main_crew"])

    def test_sets_and_clears_main_crew(self):
        response = self.client.patch(self.me_url, {"main_crew": self.crew.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["main_crew"], {"id": self.crew.id, "name": "내크루"}
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.main_crew_id, self.crew.id)

        response = self.client.patch(self.me_url, {"main_crew": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["main_crew"])

    def test_rejects_crew_i_am_not_active_in(self):
        response = self.client.patch(self.me_url, {"main_crew": self.other.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("main_crew", response.json()["error"]["fields"])

        add_member(self.other, self.user, status="pending")
        response = self.client.patch(self.me_url, {"main_crew": self.other.id})
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(self.me_url, {"main_crew": 99999})
        self.assertEqual(response.status_code, 400)
        self.assertIn("main_crew", response.json()["error"]["fields"])

    def test_public_profile_shows_main_crew(self):
        self.client.patch(self.me_url, {"main_crew": self.crew.id})
        self.client.force_authenticate(self.owner)
        data = self.client.get(self.profile_url()).json()["data"]
        self.assertEqual(data["main_crew"], {"id": self.crew.id, "name": "내크루"})

    def test_cleared_when_crew_is_deleted(self):
        self.client.patch(self.me_url, {"main_crew": self.crew.id})
        self.client.force_authenticate(self.owner)
        response = self.client.delete(
            reverse("v1:crews:crew-detail", args=[self.crew.id])
        )
        self.assertEqual(response.status_code, 204)
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.main_crew_id)
        self.client.force_authenticate(self.user)
        self.assertIsNone(self.client.get(self.me_url).json()["data"]["main_crew"])
