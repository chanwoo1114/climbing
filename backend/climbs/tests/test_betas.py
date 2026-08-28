"""베타 영상 — 공개 목록/섹터 집계/상세(조회수), 올린 사람만 수정·삭제, 업로드 kind."""

from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.models import BETA_DESCRIPTION_MAX_LENGTH, ClimbBeta
from climbs.tests.helpers import create_beta, create_difficulty, create_gym, create_log
from common.services.uploads import UPLOAD_KINDS, allowed_content_types

VIDEO = "https://cdn.example.com/beta_video/1/x.mp4"
THUMB = "https://cdn.example.com/beta_thumbnail/1/x.jpg"


class BetaTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.other = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym("암장A")
        cls.other_gym = create_gym("암장B")
        cls.green = create_difficulty(cls.gym, name="초록", order=0)
        cls.blue = create_difficulty(cls.gym, name="파랑", color="#2b5fd9", order=1)
        cls.foreign = create_difficulty(cls.other_gym, name="빨강", color="#c33")
        cls.list_url = reverse("v1:climbs:gym-betas", args=[cls.gym.id])
        cls.sectors_url = reverse("v1:climbs:gym-beta-sectors", args=[cls.gym.id])

    @staticmethod
    def detail_url(beta):
        return reverse("v1:climbs:beta-detail", args=[beta.id])


class BetaListTests(BetaTestCase):
    def setUp(self):
        self.b1 = create_beta(
            self.owner,
            self.gym,
            title="슬랩 크럭스",
            sector="A섹터",
            difficulty=self.green,
        )
        self.b2 = create_beta(
            self.other,
            self.gym,
            title="오버행 다이노",
            sector="a섹터",
            difficulty=self.blue,
        )
        self.b3 = create_beta(self.owner, self.gym, title="발 바꾸기", sector="슬랩 벽")
        create_beta(self.owner, self.other_gym, title="다른 암장")

    def test_public_list_without_auth(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        results = body["data"]["results"]
        self.assertEqual(
            [b["id"] for b in results], [self.b3.id, self.b2.id, self.b1.id]
        )
        item = results[-1]
        self.assertEqual(
            item["user"], {"id": self.owner.id, "nickname": "alpha", "image": None}
        )
        self.assertEqual(item["gym"], {"id": self.gym.id, "name": "암장A"})
        self.assertEqual(item["difficulty"]["name"], "초록")
        self.assertEqual(item["difficulty"]["order"], 0)
        self.assertEqual(item["view_count"], 0)
        self.assertIsNone(item["climb_log_id"])
        self.assertFalse(item["is_mine"])
        self.assertIsNone(results[0]["difficulty"])

    def test_is_mine_for_authenticated_user(self):
        self.client.force_authenticate(self.owner)
        results = self.client.get(self.list_url).json()["data"]["results"]
        mine = {b["id"]: b["is_mine"] for b in results}
        self.assertEqual(mine, {self.b3.id: True, self.b2.id: False, self.b1.id: True})

    def test_filter_sector_case_insensitive(self):
        results = self.client.get(self.list_url, {"sector": "A섹터"}).json()["data"][
            "results"
        ]
        self.assertEqual({b["id"] for b in results}, {self.b1.id, self.b2.id})

    def test_filter_difficulty(self):
        results = self.client.get(self.list_url, {"difficulty": self.blue.id}).json()[
            "data"
        ]["results"]
        self.assertEqual([b["id"] for b in results], [self.b2.id])

        response = self.client.get(self.list_url, {"difficulty": "abc"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("difficulty", response.json()["error"]["fields"])

    def test_filter_q_title(self):
        results = self.client.get(self.list_url, {"q": "다이노"}).json()["data"][
            "results"
        ]
        self.assertEqual([b["id"] for b in results], [self.b2.id])

    def test_unknown_or_deleted_gym_404(self):
        url = reverse("v1:climbs:gym-betas", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.other_gym.delete()
        url = reverse("v1:climbs:gym-betas", args=[self.other_gym.id])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_soft_deleted_beta_excluded(self):
        self.b2.delete()
        results = self.client.get(self.list_url).json()["data"]["results"]
        self.assertNotIn(self.b2.id, [b["id"] for b in results])
        self.assertTrue(ClimbBeta.all_objects.get(pk=self.b2.id).is_deleted)

    def test_cursor_pagination(self):
        first = self.client.get(self.list_url, {"limit": 2}).json()["data"]
        self.assertEqual(len(first["results"]), 2)
        self.assertIsNotNone(first["next_cursor"])

        second = self.client.get(first["next_cursor"]).json()["data"]
        self.assertEqual([b["id"] for b in second["results"]], [self.b1.id])
        self.assertIsNone(second["next_cursor"])

    def test_sectors_aggregation(self):
        create_beta(self.owner, self.gym, title="빈 섹터", sector="")
        response = self.client.get(self.sectors_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        # 빈 섹터 제외, 대소문자가 다른 "A섹터"/"a섹터" 는 별개 값.
        # (동률일 때의 이름순은 DB collation 에 따라 다르므로 집합으로만 확인)
        self.assertEqual(
            sorted(data, key=lambda row: row["sector"]),
            sorted(
                [
                    {"sector": "A섹터", "count": 1},
                    {"sector": "a섹터", "count": 1},
                    {"sector": "슬랩 벽", "count": 1},
                ],
                key=lambda row: row["sector"],
            ),
        )
        create_beta(self.other, self.gym, sector="슬랩 벽")
        create_beta(self.other, self.gym, sector="a섹터")
        create_beta(self.other, self.gym, sector="a섹터")
        data = self.client.get(self.sectors_url).json()["data"]
        self.assertEqual([row["count"] for row in data], [3, 2, 1])
        self.assertEqual(data[0], {"sector": "a섹터", "count": 3})
        self.assertEqual(data[1], {"sector": "슬랩 벽", "count": 2})

        url = reverse("v1:climbs:gym-beta-sectors", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)


class BetaCreateTests(BetaTestCase):
    def setUp(self):
        self.client.force_authenticate(self.owner)
        self.log = create_log(self.owner, self.gym)

    def post(self, **body):
        payload = {"title": "크럭스 풀이", "video_url": VIDEO}
        payload.update(body)
        return self.client.post(self.list_url, payload, format="json")

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.post().status_code, 401)

    def test_create_with_all_fields(self):
        response = self.post(
            sector=" B섹터 ",
            difficulty=self.blue.id,
            description="힐훅 후 왼손 크림프",
            thumbnail_url=THUMB,
            climb_log=self.log.id,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["title"], "크럭스 풀이")
        self.assertEqual(data["sector"], "B섹터")
        self.assertEqual(data["difficulty"]["id"], self.blue.id)
        self.assertEqual(data["description"], "힐훅 후 왼손 크림프")
        self.assertEqual(data["video_url"], VIDEO)
        self.assertEqual(data["thumbnail_url"], THUMB)
        self.assertEqual(data["climb_log_id"], self.log.id)
        self.assertEqual(data["gym"]["id"], self.gym.id)
        self.assertEqual(data["user"]["id"], self.owner.id)
        self.assertEqual(data["view_count"], 0)
        self.assertTrue(data["is_mine"])

        beta = ClimbBeta.objects.get(pk=data["id"])
        self.assertEqual(beta.user_id, self.owner.id)
        self.assertEqual(beta.gym_id, self.gym.id)

    def test_create_minimal(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["sector"], "")
        self.assertIsNone(data["difficulty"])
        self.assertIsNone(data["climb_log_id"])

    def test_requires_title_and_video_url(self):
        response = self.client.post(self.list_url, {"title": ""}, format="json")
        self.assertEqual(response.status_code, 400)
        fields = response.json()["error"]["fields"]
        self.assertIn("title", fields)
        self.assertIn("video_url", fields)

        response = self.post(video_url="not-a-url")
        self.assertEqual(response.status_code, 400)
        self.assertIn("video_url", response.json()["error"]["fields"])

    def test_difficulty_of_other_gym_rejected(self):
        response = self.post(difficulty=self.foreign.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("difficulty", response.json()["error"]["fields"])

    def test_climb_log_of_other_user_rejected(self):
        others_log = create_log(self.other, self.gym)
        response = self.post(climb_log=others_log.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("climb_log", response.json()["error"]["fields"])

    def test_climb_log_of_other_gym_rejected(self):
        log = create_log(self.owner, self.other_gym)
        response = self.post(climb_log=log.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("climb_log", response.json()["error"]["fields"])

    def test_description_too_long(self):
        response = self.post(description="x" * (BETA_DESCRIPTION_MAX_LENGTH + 1))
        self.assertEqual(response.status_code, 400)
        self.assertIn("description", response.json()["error"]["fields"])

    def test_unknown_gym_404(self):
        url = reverse("v1:climbs:gym-betas", args=[999999])
        response = self.client.post(
            url, {"title": "x", "video_url": VIDEO}, format="json"
        )
        self.assertEqual(response.status_code, 404)


class BetaDetailTests(BetaTestCase):
    def setUp(self):
        self.beta = create_beta(
            self.owner,
            self.gym,
            title="원본",
            difficulty=self.green,
            description="설명",
        )
        self.url = self.detail_url(self.beta)

    def test_detail_public_and_increments_view_count(self):
        first = self.client.get(self.url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["data"]["view_count"], 1)
        self.assertFalse(first.json()["data"]["is_mine"])

        second = self.client.get(self.url)
        self.assertEqual(second.json()["data"]["view_count"], 2)
        self.beta.refresh_from_db()
        self.assertEqual(self.beta.view_count, 2)

        # 목록 조회는 조회수를 올리지 않는다
        self.client.get(self.list_url)
        self.beta.refresh_from_db()
        self.assertEqual(self.beta.view_count, 2)

    def test_detail_unknown_404(self):
        url = reverse("v1:climbs:beta-detail", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_patch_by_owner(self):
        self.client.force_authenticate(self.owner)
        log = create_log(self.owner, self.gym)
        response = self.client.patch(
            self.url,
            {
                "title": "수정됨",
                "sector": "C섹터",
                "difficulty": self.blue.id,
                "description": "새 설명",
                "thumbnail_url": THUMB,
                "climb_log": log.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["title"], "수정됨")
        self.assertEqual(data["sector"], "C섹터")
        self.assertEqual(data["difficulty"]["id"], self.blue.id)
        self.assertEqual(data["description"], "새 설명")
        self.assertEqual(data["thumbnail_url"], THUMB)
        self.assertEqual(data["climb_log_id"], log.id)
        self.assertTrue(data["is_mine"])

        # 난이도/기록 해제
        response = self.client.patch(
            self.url, {"difficulty": None, "climb_log": None}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["difficulty"])
        self.assertIsNone(response.json()["data"]["climb_log_id"])

    def test_patch_validates_difficulty_and_log_against_beta_gym(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            self.url, {"difficulty": self.foreign.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("difficulty", response.json()["error"]["fields"])

        log = create_log(self.owner, self.other_gym)
        response = self.client.patch(self.url, {"climb_log": log.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("climb_log", response.json()["error"]["fields"])

    def test_patch_by_other_403_and_anonymous_401(self):
        self.client.force_authenticate(self.other)
        response = self.client.patch(self.url, {"title": "해킹"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.beta.refresh_from_db()
        self.assertEqual(self.beta.title, "원본")

        self.client.force_authenticate(None)
        response = self.client.patch(self.url, {"title": "익명"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_video_url_not_editable(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            self.url, {"video_url": "https://cdn.example.com/other.mp4"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("video_url", response.json()["error"]["fields"])
        self.beta.refresh_from_db()
        self.assertEqual(
            self.beta.video_url, "https://cdn.example.com/beta_video/1/a.mp4"
        )

    def test_delete_by_owner_soft_deletes(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertTrue(ClimbBeta.all_objects.get(pk=self.beta.id).is_deleted)

        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.delete(self.url).status_code, 404)

    def test_delete_by_other_403(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.assertTrue(ClimbBeta.objects.filter(pk=self.beta.id).exists())


@override_settings(
    AWS_ACCESS_KEY_ID="test-key",
    AWS_SECRET_ACCESS_KEY="test-secret",
    AWS_STORAGE_BUCKET_NAME="test-bucket",
    AWS_S3_REGION_NAME="ap-northeast-2",
    AWS_S3_ENDPOINT_URL=None,
    MEDIA_PUBLIC_BASE_URL="",
    S3_PRESIGNED_EXPIRE_SECONDS=300,
)
class BetaUploadKindTests(APITestCase):
    """beta_video / beta_thumbnail 업로드 종류가 presigned URL 발급에 열려 있다."""

    url = reverse("v1:common:presigned-url")

    def setUp(self):
        self.user = create_verified_user()
        self.client.force_authenticate(self.user)

    def test_upload_kinds_registered(self):
        self.assertIn("beta_video", UPLOAD_KINDS)
        self.assertIn("beta_thumbnail", UPLOAD_KINDS)
        self.assertIn("video/mp4", allowed_content_types("beta_video"))
        self.assertIn("image/jpeg", allowed_content_types("beta_thumbnail"))
        self.assertNotIn("image/jpeg", allowed_content_types("beta_video"))

    @patch("common.services.uploads.boto3.client")
    def test_presigned_url_accepts_beta_video(self, client_factory):
        client_factory.return_value.generate_presigned_url.return_value = "https://x"
        response = self.client.post(
            self.url,
            {"kind": "beta_video", "filename": "beta.mp4", "content_type": "video/mp4"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["key"].startswith(f"beta_video/{self.user.pk}/"))
        self.assertTrue(data["key"].endswith(".mp4"))
        self.assertEqual(data["max_bytes"], 200 * 1024 * 1024)

    @patch("common.services.uploads.boto3.client")
    def test_presigned_url_accepts_beta_thumbnail(self, client_factory):
        client_factory.return_value.generate_presigned_url.return_value = "https://x"
        response = self.client.post(
            self.url,
            {
                "kind": "beta_thumbnail",
                "filename": "t.png",
                "content_type": "image/png",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["max_bytes"], 5 * 1024 * 1024)
