"""크루장 위임 (POST crews/{id}/transfer/) 과 크루 목록 지역 필터 (?region=)."""

from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import PASSWORD, create_verified_user
from crews.models import Crew, CrewMember
from crews.tests.helpers import add_member, create_crew
from gyms.models import Gym
from notifications.models import Notification
from notifications.tests.helpers import IN_MEMORY_CHANNELS


@override_settings(**IN_MEMORY_CHANNELS)
class CrewOwnerTransferTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.member = create_verified_user(email="b@example.com", nickname="bravo")
        cls.applicant = create_verified_user(email="c@example.com", nickname="charlie")
        cls.outsider = create_verified_user(email="d@example.com", nickname="delta")

    def setUp(self):
        self.crew = create_crew(self.owner)
        add_member(self.crew, self.member)
        add_member(self.crew, self.applicant, status="pending")
        self.url = reverse("v1:crews:crew-transfer", args=[self.crew.id])

    def _transfer(self, actor, user_id):
        self.client.force_authenticate(actor)
        return self.client.post(self.url, {"user_id": user_id})

    def _role(self, user):
        return CrewMember.objects.get(crew=self.crew, user=user).role

    def test_requires_auth(self):
        self.assertEqual(self.client.post(self.url, {"user_id": 1}).status_code, 401)

    def test_owner_transfers_to_active_member(self):
        response = self._transfer(self.owner, self.member.id)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["owner"]["id"], self.member.id)
        self.assertEqual(data["my_status"], "staff")  # 기존 크루장은 운영진으로

        self.crew.refresh_from_db()
        self.assertEqual(self.crew.owner_id, self.member.id)
        self.assertEqual(self._role(self.member), CrewMember.Role.OWNER)
        self.assertEqual(self._role(self.owner), CrewMember.Role.STAFF)

        # 새 크루장에게 알림
        items = list(Notification.objects.filter(recipient=self.member))
        self.assertEqual([n.type for n in items], ["crew_owner"])
        self.assertEqual(items[0].actor_id, self.owner.id)
        self.assertEqual(
            (items[0].target_type, items[0].target_id), ("crew", self.crew.id)
        )

    def test_only_owner_can_transfer(self):
        add_member(self.crew, self.outsider, role="staff")
        self.assertEqual(self._transfer(self.outsider, self.member.id).status_code, 403)
        self.assertEqual(self._transfer(self.member, self.owner.id).status_code, 403)
        self.crew.refresh_from_db()
        self.assertEqual(self.crew.owner_id, self.owner.id)

    def test_target_must_be_active_member(self):
        for target in (self.applicant, self.outsider):
            response = self._transfer(self.owner, target.id)
            self.assertEqual(response.status_code, 400)
            self.assertIn("user_id", response.json()["error"]["fields"])
        self.assertEqual(self._transfer(self.owner, 999999).status_code, 400)

    def test_cannot_transfer_to_self(self):
        response = self._transfer(self.owner, self.owner.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("user_id", response.json()["error"]["fields"])

    def test_old_owner_can_leave_and_withdraw_after_transfer(self):
        self.assertEqual(self._transfer(self.owner, self.member.id).status_code, 200)

        self.client.force_authenticate(self.owner)
        leave = self.client.delete(reverse("v1:crews:crew-leave", args=[self.crew.id]))
        self.assertEqual(leave.status_code, 204)
        self.assertFalse(
            CrewMember.objects.filter(crew=self.crew, user=self.owner).exists()
        )

        withdraw = self.client.delete(reverse("v1:accounts:me"), {"password": PASSWORD})
        self.assertEqual(withdraw.status_code, 204)

    def test_new_owner_cannot_leave(self):
        self.assertEqual(self._transfer(self.owner, self.member.id).status_code, 200)
        self.client.force_authenticate(self.member)
        leave = self.client.delete(reverse("v1:crews:crew-leave", args=[self.crew.id]))
        self.assertEqual(leave.status_code, 400)

    def test_unknown_crew_404(self):
        self.client.force_authenticate(self.owner)
        url = reverse("v1:crews:crew-transfer", args=[999999])
        self.assertEqual(
            self.client.post(url, {"user_id": self.member.id}).status_code, 404
        )


class CrewRegionFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_verified_user()
        cls.url = reverse("v1:crews:crew-list")
        gangnam = Gym.objects.create(
            name="강남암장",
            address="서울 강남구 테헤란로 1",
            location=Point(127.03, 37.5, srid=4326),
        )
        suwon = Gym.objects.create(
            name="수원암장",
            address="경기 수원시 팔달구 2",
            location=Point(127.0, 37.27, srid=4326),
        )
        cls.gangnam_crew = create_crew(cls.user, name="강남크루", home_gym=gangnam)
        cls.suwon_crew = create_crew(cls.user, name="수원크루", home_gym=suwon)
        cls.no_gym_crew = create_crew(cls.user, name="홈짐없음")

    def _ids(self, **params):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return {c["id"] for c in response.json()["data"]["results"]}

    def test_region_matches_home_gym_address(self):
        self.assertEqual(self._ids(region="강남구"), {self.gangnam_crew.id})
        self.assertEqual(self._ids(region="경기"), {self.suwon_crew.id})
        self.assertEqual(self._ids(region="서울"), {self.gangnam_crew.id})

    def test_region_combines_with_name_search(self):
        self.assertEqual(self._ids(region="서울", q="수원"), set())
        self.assertEqual(self._ids(region="서울", q="강남"), {self.gangnam_crew.id})

    def test_blank_region_returns_all(self):
        self.assertEqual(
            self._ids(region=" "),
            {self.gangnam_crew.id, self.suwon_crew.id, self.no_gym_crew.id},
        )
        self.assertEqual(Crew.objects.count(), 3)
