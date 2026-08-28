"""게시글 목록 검색 — ?q= 제목·본문 부분 일치 (대소문자 무시), 다른 필터와 AND."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from community.models import Post
from community.tests.helpers import create_post


class PostSearchTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_verified_user()
        cls.url = reverse("v1:community:post-list")
        cls.title_hit = create_post(
            cls.user, title="강남 볼더링 같이 가요", content="본문"
        )
        cls.content_hit = create_post(
            cls.user, title="제목", content="이번 주말 Bouldering 세션 모집"
        )
        cls.miss = create_post(cls.user, title="리드 클라이밍", content="자유글")

    def setUp(self):
        self.client.force_authenticate(self.user)

    def _ids(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return {item["id"] for item in response.json()["data"]["results"]}

    def test_matches_title_and_content(self):
        self.assertEqual(self._ids(q="볼더링"), {self.title_hit.id})
        self.assertEqual(self._ids(q="세션"), {self.content_hit.id})

    def test_case_insensitive(self):
        self.assertEqual(self._ids(q="bouldering"), {self.content_hit.id})

    def test_blank_query_returns_all(self):
        self.assertEqual(
            self._ids(q="  "), {self.title_hit.id, self.content_hit.id, self.miss.id}
        )

    def test_no_match_is_empty(self):
        self.assertEqual(self._ids(q="없는말"), set())

    def test_combines_with_category_filter(self):
        create_post(self.user, category=Post.Category.RECRUIT, title="볼더링 모집")
        # 카테고리 필터와 AND — 자유글 중 '볼더링' 만
        self.assertEqual(
            self._ids(q="볼더링", category=Post.Category.FREE), {self.title_hit.id}
        )
