"""암장 관리자 — 권한(관리자/운영자/일반/비로그인), 내 관리 암장, 암장 정보 수정, 관리자 관리."""

from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from gyms.models import Gym, GymManager


def create_gym(name="관리암장") -> Gym:
    return Gym.objects.create(
        name=name, address="서울", location=Point(127.0, 37.5, srid=4326)
    )


def create_staff(email="staff@example.com", nickname="운영자"):
    user = create_verified_user(email=email, nickname=nickname)
    user.is_staff = True
    user.save(update_fields=["is_staff", "updated_at"])
    return user


class ManagerBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gym = create_gym()
        cls.other_gym = create_gym("다른암장")
        cls.manager = create_verified_user(email="mgr@example.com", nickname="점장")
        cls.member = create_verified_user(email="member@example.com", nickname="회원")
        cls.staff = create_staff()
        GymManager.objects.create(gym=cls.gym, user=cls.manager)


class ManagedGymListTests(ManagerBase):
    url = reverse("v1:gyms:managed")

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_lists_only_my_gyms(self):
        GymManager.objects.create(gym=self.other_gym, user=self.member)
        self.client.force_authenticate(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([g["id"] for g in data], [self.gym.id])
        self.assertIsNone(data[0]["distance_m"])
        self.assertIn("thumbnail", data[0])

    def test_staff_gets_only_explicit_rows(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.url).json()["data"], [])

    def test_removed_manager_gym_disappears(self):
        GymManager.objects.get(gym=self.gym, user=self.manager).delete()
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get(self.url).json()["data"], [])


class GymPatchTests(ManagerBase):
    def url(self):
        return reverse("v1:gyms:detail", args=[self.gym.id])

    def test_anonymous_401(self):
        response = self.client.patch(self.url(), {"name": "x"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_non_manager_403(self):
        self.client.force_authenticate(self.member)
        response = self.client.patch(self.url(), {"name": "x"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["message"], "암장 관리자만 할 수 있습니다."
        )

    def test_manager_can_patch(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            self.url(),
            {"name": "새이름", "phone": "02-123-4567", "description": "소개"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["name"], "새이름")
        self.assertEqual(data["phone"], "02-123-4567")
        self.assertTrue(data["is_manager"])
        self.assertIn("review_count", data)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.description, "소개")

    def test_staff_can_patch(self):
        self.client.force_authenticate(self.staff)
        response = self.client.patch(self.url(), {"name": "운영자수정"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["name"], "운영자수정")

    def test_location_is_ignored(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            self.url(),
            {"lat": 1.0, "lng": 2.0, "location": "POINT(1 2)", "address": "부산"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.address, "부산")
        self.assertAlmostEqual(self.gym.location.y, 37.5)
        self.assertAlmostEqual(self.gym.location.x, 127.0)

    def test_invalid_website_400(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            self.url(), {"website": "not-a-url"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("website", response.json()["error"]["fields"])

    def test_put_not_allowed(self):
        self.client.force_authenticate(self.manager)
        response = self.client.put(self.url(), {"name": "x"}, format="json")
        self.assertEqual(response.status_code, 405)


class GymDetailIsManagerTests(ManagerBase):
    def get(self):
        return self.client.get(reverse("v1:gyms:detail", args=[self.gym.id])).json()[
            "data"
        ]

    def test_anonymous_false(self):
        self.assertFalse(self.get()["is_manager"])

    def test_member_false(self):
        self.client.force_authenticate(self.member)
        self.assertFalse(self.get()["is_manager"])

    def test_manager_true(self):
        self.client.force_authenticate(self.manager)
        self.assertTrue(self.get()["is_manager"])

    def test_staff_true(self):
        self.client.force_authenticate(self.staff)
        self.assertTrue(self.get()["is_manager"])

    def test_other_gym_false_for_manager(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(reverse("v1:gyms:detail", args=[self.other_gym.id]))
        self.assertFalse(response.json()["data"]["is_manager"])


class GymManagerListTests(ManagerBase):
    def url(self):
        return reverse("v1:gyms:managers", args=[self.gym.id])

    def test_anonymous_401(self):
        self.assertEqual(self.client.get(self.url()).status_code, 401)

    def test_non_manager_403(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_manager_sees_list(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["user"]["id"], self.manager.id)
        self.assertEqual(data[0]["user"]["nickname"], "점장")
        self.assertIn("image", data[0]["user"])
        self.assertIn("created_at", data[0])

    def test_staff_sees_list(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_missing_gym_404(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse("v1:gyms:managers", args=[99999]))
        self.assertEqual(response.status_code, 404)


class GymManagerAddTests(ManagerBase):
    def url(self):
        return reverse("v1:gyms:managers", args=[self.gym.id])

    def test_non_manager_403(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.url(), {"user_id": self.member.id}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_adds_user(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.url(), {"user_id": self.member.id, "note": "부점장"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["user"]["id"], self.member.id)
        self.assertEqual(data["note"], "부점장")
        row = GymManager.objects.get(gym=self.gym, user=self.member)
        self.assertEqual(row.assigned_by_id, self.manager.id)

    def test_add_is_idempotent(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.url(), {"user_id": self.manager.id}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GymManager.objects.filter(gym=self.gym).count(), 1)

    def test_add_restores_soft_deleted_row(self):
        row = GymManager.objects.create(gym=self.gym, user=self.member, note="옛날")
        row.delete()
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.url(), {"user_id": self.member.id, "note": "복귀"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(GymManager.all_objects.filter(gym=self.gym).count(), 2)
        row.refresh_from_db()
        self.assertFalse(row.is_deleted)
        self.assertEqual(row.note, "복귀")

    def test_unknown_user_404(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(self.url(), {"user_id": 99999}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_soft_deleted_user_404(self):
        gone = create_verified_user(email="gone@example.com", nickname="탈퇴")
        gone.delete()
        self.client.force_authenticate(self.manager)
        response = self.client.post(self.url(), {"user_id": gone.id}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_staff_can_add(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self.url(), {"user_id": self.member.id}, format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_missing_user_id_400(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(self.url(), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("user_id", response.json()["error"]["fields"])


class GymManagerRemoveTests(ManagerBase):
    def url(self, user_id):
        return reverse("v1:gyms:manager-detail", args=[self.gym.id, user_id])

    def test_anonymous_401(self):
        self.assertEqual(self.client.delete(self.url(self.manager.id)).status_code, 401)

    def test_non_manager_403(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.delete(self.url(self.manager.id)).status_code, 403)

    def test_manager_removes_other(self):
        GymManager.objects.create(gym=self.gym, user=self.member)
        self.client.force_authenticate(self.manager)
        response = self.client.delete(self.url(self.member.id))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            GymManager.objects.filter(gym=self.gym, user=self.member).exists()
        )
        self.assertTrue(
            GymManager.all_objects.filter(
                gym=self.gym, user=self.member, is_deleted=True
            ).exists()
        )

    def test_manager_can_remove_self_when_not_last(self):
        GymManager.objects.create(gym=self.gym, user=self.member)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.delete(self.url(self.manager.id)).status_code, 204)
        # 해제된 뒤엔 더 이상 관리자 API 를 못 쓴다
        self.assertEqual(
            self.client.get(
                reverse("v1:gyms:managers", args=[self.gym.id])
            ).status_code,
            403,
        )

    def test_last_manager_409(self):
        self.client.force_authenticate(self.manager)
        response = self.client.delete(self.url(self.manager.id))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "last_manager")
        self.assertTrue(
            GymManager.objects.filter(gym=self.gym, user=self.manager).exists()
        )

    def test_staff_can_remove_last_manager(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.delete(self.url(self.manager.id)).status_code, 204)
        self.assertFalse(GymManager.objects.filter(gym=self.gym).exists())

    def test_not_a_manager_404(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.delete(self.url(self.member.id)).status_code, 404)

    def test_wrong_gym_403(self):
        """다른 암장 관리자는 이 암장 관리자를 건드릴 수 없다."""
        GymManager.objects.create(gym=self.other_gym, user=self.member)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.delete(self.url(self.manager.id)).status_code, 403)
