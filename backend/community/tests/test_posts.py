"""게시글 — 목록/필터/작성(자유·모집)/상세 조회수/수정·삭제 권한."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from community.models import Post, PostImage, Recruitment
from community.tests.helpers import (
    create_gym,
    create_post,
    create_recruit_post,
    future_iso,
)


class PostListCreateTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.other_gym = create_gym("다른암장")
        cls.url = reverse("v1:community:post-list")

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url, {}).status_code, 401)

    def test_list_newest_first_with_preview_and_filters(self):
        free = create_post(self.author, title="자유", content="가" * 300)
        recruit = create_recruit_post(self.author, self.gym)
        create_post(self.author, title="다른 암장", gym=self.other_gym)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[-1]["id"], free.id)  # 최신순
        self.assertNotIn("content", results[-1])
        self.assertEqual(len(results[-1]["preview"]), 200)
        self.assertIsNone(results[-1]["recruitment"])
        self.assertEqual(results[-1]["comment_count"], 0)

        by_category = self.client.get(self.url, {"category": "recruit"}).json()
        self.assertEqual(
            [p["id"] for p in by_category["data"]["results"]], [recruit.id]
        )
        self.assertEqual(
            by_category["data"]["results"][0]["recruitment"]["status"], "open"
        )

        by_gym = self.client.get(self.url, {"gym": self.other_gym.id}).json()
        self.assertEqual(len(by_gym["data"]["results"]), 1)
        self.assertEqual(by_gym["data"]["results"][0]["gym"]["name"], "다른암장")

        self.assertEqual(self.client.get(self.url, {"category": "x"}).status_code, 400)

    def test_create_free_post_with_images(self):
        payload = {
            "category": "free",
            "title": "첫 글",
            "content": "안녕하세요",
            "gym": self.gym.id,
            "images": [
                "https://cdn.example.com/1.jpg",
                "https://cdn.example.com/2.jpg",
            ],
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["user"]["nickname"], "bravo")
        self.assertEqual(data["gym"]["id"], self.gym.id)
        self.assertEqual(data["images"], payload["images"])
        self.assertEqual(data["view_count"], 0)
        self.assertIsNone(data["recruitment"])
        self.assertEqual(PostImage.objects.filter(post_id=data["id"]).count(), 2)

    def test_create_recruit_post_atomically(self):
        payload = {
            "category": "recruit",
            "title": "주말 투어",
            "content": "같이 가요",
            "recruitment": {
                "gym": self.gym.id,
                "meet_at": future_iso(),
                "capacity": 4,
                "join_type": "approval",
            },
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        rec = data["recruitment"]
        self.assertEqual(rec["gym"]["id"], self.gym.id)
        self.assertEqual(rec["capacity"], 4)
        self.assertEqual(rec["join_type"], "approval")
        self.assertEqual(rec["status"], "open")
        self.assertEqual(rec["approved_count"], 0)
        self.assertIsNone(rec["my_participation_status"])
        self.assertIsNone(rec["chat_room_id"])
        # 관련 암장을 안 주면 모집 대상 암장이 기본값
        self.assertEqual(data["gym"]["id"], self.gym.id)
        self.assertTrue(Recruitment.objects.filter(post_id=data["id"]).exists())

    def test_recruit_post_validation(self):
        base = {"category": "recruit", "title": "t", "content": "c"}
        # recruitment 누락
        response = self.client.post(self.url, base, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("recruitment", response.json()["error"]["fields"])
        self.assertEqual(Post.objects.count(), 0)

        # 과거 일시 / 정원 범위
        for bad in (
            {"gym": self.gym.id, "meet_at": future_iso(-1), "capacity": 3},
            {"gym": self.gym.id, "meet_at": future_iso(), "capacity": 1},
            {"gym": self.gym.id, "meet_at": future_iso(), "capacity": 51},
        ):
            response = self.client.post(
                self.url, {**base, "recruitment": bad}, format="json"
            )
            self.assertEqual(response.status_code, 400, bad)
        self.assertEqual(Post.objects.count(), 0)
        self.assertEqual(Recruitment.objects.count(), 0)

        # 자유글에 recruitment
        response = self.client.post(
            self.url,
            {
                **base,
                "category": "free",
                "recruitment": {
                    "gym": self.gym.id,
                    "meet_at": future_iso(),
                    "capacity": 3,
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_title_content_validation(self):
        response = self.client.post(
            self.url, {"title": "", "content": "c"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self.url, {"title": "가" * 101, "content": "c"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self.url, {"title": "t", "content": "가" * 5001}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class PostDetailTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()

    def setUp(self):
        self.post = create_post(self.author, title="원본", content="본문")
        self.url = reverse("v1:community:post-detail", args=[self.post.id])
        self.client.force_authenticate(self.user)

    def test_view_count_increments_except_author(self):
        self.assertEqual(self.client.get(self.url).json()["data"]["view_count"], 1)
        self.assertEqual(self.client.get(self.url).json()["data"]["view_count"], 2)

        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.get(self.url).json()["data"]["view_count"], 2)
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 2)

    def test_detail_has_full_content(self):
        data = self.client.get(self.url).json()["data"]
        self.assertEqual(data["content"], "본문")
        self.assertNotIn("preview", data)

    def test_missing_404(self):
        url = reverse("v1:community:post-detail", args=[99999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_author_can_patch(self):
        self.client.force_authenticate(self.author)
        response = self.client.patch(
            self.url,
            {"title": "수정", "images": ["https://cdn.example.com/x.jpg"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["title"], "수정")
        self.assertEqual(data["content"], "본문")
        self.assertEqual(data["images"], ["https://cdn.example.com/x.jpg"])

        # 이미지 전체 교체 — 이전 이미지는 soft delete
        self.client.patch(self.url, {"images": []}, format="json")
        self.assertEqual(PostImage.objects.filter(post=self.post).count(), 0)
        self.assertEqual(PostImage.all_objects.filter(post=self.post).count(), 1)

    def test_category_cannot_change(self):
        self.client.force_authenticate(self.author)
        response = self.client.patch(self.url, {"category": "recruit"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_author_can_patch_recruitment(self):
        post = create_recruit_post(self.author, self.gym, capacity=3)
        url = reverse("v1:community:post-detail", args=[post.id])
        self.client.force_authenticate(self.author)
        response = self.client.patch(
            url, {"recruitment": {"capacity": 5}}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["recruitment"]["capacity"], 5)

    def test_other_cannot_patch_or_delete(self):
        response = self.client.patch(self.url, {"title": "해킹"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "원본")

    def test_author_delete_is_soft_and_cascades(self):
        post = create_recruit_post(self.author, self.gym)
        PostImage.objects.create(post=post, image="https://cdn.example.com/1.jpg")
        url = reverse("v1:community:post-detail", args=[post.id])
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.delete(url).status_code, 204)

        self.assertFalse(Post.objects.filter(pk=post.id).exists())
        self.assertTrue(Post.all_objects.get(pk=post.id).is_deleted)
        self.assertFalse(Recruitment.objects.filter(post_id=post.id).exists())
        self.assertFalse(PostImage.objects.filter(post_id=post.id).exists())
        self.assertEqual(self.client.get(url).status_code, 404)
