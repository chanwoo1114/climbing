"""암장 콘텐츠 관리 — 난이도/사진/가격표/편의시설 편집 (관리자·운영자만)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.tests.helpers import create_difficulty, create_gym, create_log
from gyms.models import GymDifficulty, GymFacility, GymImage, GymManager, GymPrice


class ContentBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gym = create_gym("콘텐츠암장")
        cls.manager = create_verified_user(email="mgr@example.com", nickname="점장")
        cls.member = create_verified_user(email="member@example.com", nickname="회원")
        GymManager.objects.create(gym=cls.gym, user=cls.manager)

    def as_manager(self):
        self.client.force_authenticate(self.manager)

    def detail(self):
        return self.client.get(reverse("v1:gyms:detail", args=[self.gym.id])).json()[
            "data"
        ]


class DifficultyCreateTests(ContentBase):
    def url(self):
        return reverse("v1:gyms:difficulties", args=[self.gym.id])

    def test_list_stays_public(self):
        create_difficulty(self.gym)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)

    def test_anonymous_401(self):
        response = self.client.post(
            self.url(), {"name": "초록", "color": "#5f7d4e"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_non_manager_403(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.url(), {"name": "초록", "color": "#5f7d4e"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_creates(self):
        self.as_manager()
        response = self.client.post(
            self.url(), {"name": "초록", "color": "#5F7D4E", "order": 3}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["name"], "초록")
        self.assertEqual(data["color"], "#5f7d4e")  # 소문자로 정규화
        self.assertEqual(data["order"], 3)
        self.assertTrue(
            GymDifficulty.objects.filter(gym=self.gym, name="초록").exists()
        )

    def test_duplicate_live_name_400(self):
        create_difficulty(self.gym, name="초록")
        self.as_manager()
        response = self.client.post(
            self.url(), {"name": "초록", "color": "#000000"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["error"]["fields"])

    def test_deleted_name_can_be_reused(self):
        create_difficulty(self.gym, name="초록").delete()
        self.as_manager()
        response = self.client.post(
            self.url(), {"name": "초록", "color": "#000000"}, format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_invalid_color_400(self):
        self.as_manager()
        for bad in ("5f7d4e", "#5f7", "#gggggg", "red", "#5f7d4e1"):
            response = self.client.post(
                self.url(), {"name": bad, "color": bad}, format="json"
            )
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn("color", response.json()["error"]["fields"])

    def test_missing_gym_404(self):
        self.as_manager()
        response = self.client.post(
            reverse("v1:gyms:difficulties", args=[99999]),
            {"name": "초록", "color": "#000000"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class DifficultyUpdateDeleteTests(ContentBase):
    def setUp(self):
        self.green = create_difficulty(self.gym, name="초록", order=0)
        self.red = create_difficulty(self.gym, name="빨강", color="#c04a38", order=1)

    def url(self, difficulty):
        return reverse("v1:gyms:difficulty-detail", args=[self.gym.id, difficulty.id])

    def test_anonymous_401(self):
        response = self.client.patch(self.url(self.green), {"name": "x"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_non_manager_403(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.patch(
                self.url(self.green), {"name": "x"}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(self.client.delete(self.url(self.green)).status_code, 403)

    def test_patch(self):
        self.as_manager()
        response = self.client.patch(
            self.url(self.green), {"name": "연두", "order": 5}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.green.refresh_from_db()
        self.assertEqual((self.green.name, self.green.order), ("연두", 5))

    def test_patch_to_existing_name_400(self):
        self.as_manager()
        response = self.client.patch(
            self.url(self.green), {"name": "빨강"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["error"]["fields"])

    def test_patch_same_name_ok(self):
        self.as_manager()
        response = self.client.patch(
            self.url(self.green), {"name": "초록", "color": "#111111"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

    def test_patch_bad_color_400(self):
        self.as_manager()
        response = self.client.patch(
            self.url(self.green), {"color": "green"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_is_soft(self):
        self.as_manager()
        self.assertEqual(self.client.delete(self.url(self.green)).status_code, 204)
        self.assertFalse(GymDifficulty.objects.filter(pk=self.green.pk).exists())
        self.assertTrue(
            GymDifficulty.all_objects.filter(pk=self.green.pk, is_deleted=True).exists()
        )
        self.assertEqual([d["name"] for d in self.detail()["difficulties"]], ["빨강"])
        # 두 번째 삭제는 404
        self.assertEqual(self.client.delete(self.url(self.green)).status_code, 404)

    def test_difficulty_of_other_gym_404(self):
        other = create_gym("다른암장")
        foreign = create_difficulty(other, name="남의것")
        self.as_manager()
        self.assertEqual(self.client.delete(self.url(foreign)).status_code, 404)

    def test_log_referencing_deleted_difficulty_still_serializes(self):
        """기록이 가리키는 난이도를 지워도 기록 상세/목록은 난이도를 계속 보여준다."""
        log = create_log(self.member, self.gym, difficulty=self.green)
        self.as_manager()
        self.client.delete(self.url(self.green))

        self.client.force_authenticate(self.member)
        response = self.client.get(reverse("v1:climbs:log-detail", args=[log.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["difficulty"]["name"], "초록")

        log.refresh_from_db()
        self.assertEqual(
            log.difficulty_id, self.green.id
        )  # SET_NULL 은 hard delete 전용


class ImageTests(ContentBase):
    def create_url(self):
        return reverse("v1:gyms:images", args=[self.gym.id])

    def test_anonymous_401(self):
        response = self.client.post(
            self.create_url(), {"image": "https://cdn.example.com/a.jpg"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_non_manager_403(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.create_url(), {"image": "https://cdn.example.com/a.jpg"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_add_appends_to_end(self):
        GymImage.objects.create(gym=self.gym, image="https://cdn.example.com/0.jpg")
        self.as_manager()
        response = self.client.post(
            self.create_url(), {"image": "https://cdn.example.com/a.jpg"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["order"], 1)
        self.assertEqual(data["image"], "https://cdn.example.com/a.jpg")

    def test_add_with_explicit_order(self):
        self.as_manager()
        response = self.client.post(
            self.create_url(),
            {"image": "https://cdn.example.com/a.jpg", "order": 7},
            format="json",
        )
        self.assertEqual(response.json()["data"]["order"], 7)

    def test_invalid_url_400(self):
        self.as_manager()
        response = self.client.post(
            self.create_url(), {"image": "not a url"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_delete(self):
        image = GymImage.objects.create(
            gym=self.gym, image="https://cdn.example.com/0.jpg"
        )
        url = reverse("v1:gyms:image-detail", args=[self.gym.id, image.id])
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.as_manager()
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(GymImage.objects.filter(pk=image.pk).exists())
        self.assertEqual(self.detail()["images"], [])

    def test_delete_image_of_other_gym_404(self):
        other = create_gym("다른암장")
        image = GymImage.objects.create(
            gym=other, image="https://cdn.example.com/x.jpg"
        )
        self.as_manager()
        url = reverse("v1:gyms:image-detail", args=[self.gym.id, image.id])
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_reorder(self):
        a, b, c = (
            GymImage.objects.create(
                gym=self.gym, image=f"https://cdn.example.com/{i}.jpg", order=i
            )
            for i in range(3)
        )
        url = reverse("v1:gyms:image-order", args=[self.gym.id])
        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.put(
                url, {"ids": [c.id, a.id, b.id]}, format="json"
            ).status_code,
            403,
        )
        self.as_manager()
        response = self.client.put(url, {"ids": [c.id, a.id]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [img["id"] for img in response.json()["data"]], [c.id, a.id, b.id]
        )
        self.assertEqual(
            [img["id"] for img in self.detail()["images"]], [c.id, a.id, b.id]
        )

    def test_reorder_with_foreign_or_duplicate_id_400(self):
        a = GymImage.objects.create(gym=self.gym, image="https://cdn.example.com/a.jpg")
        other = create_gym("다른암장")
        foreign = GymImage.objects.create(
            gym=other, image="https://cdn.example.com/x.jpg"
        )
        url = reverse("v1:gyms:image-order", args=[self.gym.id])
        self.as_manager()
        response = self.client.put(url, {"ids": [a.id, foreign.id]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("ids", response.json()["error"]["fields"])
        response = self.client.put(url, {"ids": [a.id, a.id]}, format="json")
        self.assertEqual(response.status_code, 400)


class PriceReplaceTests(ContentBase):
    def url(self):
        return reverse("v1:gyms:prices", args=[self.gym.id])

    def test_permissions(self):
        self.assertEqual(
            self.client.put(self.url(), [], format="json").status_code, 401
        )
        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.put(self.url(), [], format="json").status_code, 403
        )

    def test_replace(self):
        old = GymPrice.objects.create(gym=self.gym, name="1일권", price=20000)
        self.as_manager()
        response = self.client.put(
            self.url(),
            [
                {"name": "1일권", "price": 25000, "note": "장비 별도"},
                {"name": "월회원권", "price": 150000},
            ],
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([p["name"] for p in data], ["1일권", "월회원권"])
        self.assertEqual(data[0]["note"], "장비 별도")
        self.assertEqual(data[1]["note"], "")

        old.refresh_from_db()
        self.assertTrue(old.is_deleted)
        self.assertEqual(GymPrice.objects.filter(gym=self.gym).count(), 2)
        self.assertEqual([p["price"] for p in self.detail()["prices"]], [25000, 150000])

    def test_empty_list_clears(self):
        GymPrice.objects.create(gym=self.gym, name="1일권", price=20000)
        self.as_manager()
        response = self.client.put(self.url(), [], format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])
        self.assertEqual(self.detail()["prices"], [])

    def test_invalid_item_rejects_whole_request(self):
        GymPrice.objects.create(gym=self.gym, name="1일권", price=20000)
        self.as_manager()
        response = self.client.put(
            self.url(),
            [{"name": "1일권", "price": 25000}, {"name": "", "price": -1}],
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(GymPrice.objects.filter(gym=self.gym).count(), 1)  # 그대로

    def test_non_list_body_400(self):
        self.as_manager()
        response = self.client.put(
            self.url(), {"name": "1일권", "price": 1}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class FacilityReplaceTests(ContentBase):
    def url(self):
        return reverse("v1:gyms:facilities", args=[self.gym.id])

    def test_permissions(self):
        self.assertEqual(
            self.client.put(self.url(), [], format="json").status_code, 401
        )
        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.put(self.url(), [], format="json").status_code, 403
        )

    def test_replace(self):
        old = GymFacility.objects.create(gym=self.gym, name="샤워실")
        self.as_manager()
        response = self.client.put(
            self.url(), [{"name": "주차장"}, {"name": "락커"}], format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [f["name"] for f in response.json()["data"]], ["주차장", "락커"]
        )
        old.refresh_from_db()
        self.assertTrue(old.is_deleted)
        self.assertEqual(
            [f["name"] for f in self.detail()["facilities"]], ["주차장", "락커"]
        )

    def test_empty_list_clears(self):
        GymFacility.objects.create(gym=self.gym, name="샤워실")
        self.as_manager()
        self.assertEqual(
            self.client.put(self.url(), [], format="json").status_code, 200
        )
        self.assertEqual(self.detail()["facilities"], [])
