"""피드 — explore(전체 공개)/following(팔로잉) 범위, 최신순 커서, 쿼리 수."""

from django.apps import apps
from django.db import connection
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.models import ClimbLogComment, ClimbLogLike
from climbs.tests.helpers import create_difficulty, create_gym, create_log


def get_follow_model():
    """social.Follow — 모델이 없거나(동시 개발 중) 테이블이 아직 없으면 None."""
    try:
        model = apps.get_model("social", "Follow")
    except LookupError:
        return None
    if model._meta.db_table not in connection.introspection.table_names():
        return None
    return model


class FeedTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="me@example.com", nickname="me")
        cls.friend = create_verified_user(email="f@example.com", nickname="friend")
        cls.stranger = create_verified_user(email="s@example.com", nickname="stranger")
        cls.gym = create_gym()
        cls.difficulty = create_difficulty(cls.gym)

        cls.friend_log = create_log(cls.friend, cls.gym, difficulty=cls.difficulty)
        cls.friend_private = create_log(cls.friend, cls.gym, is_shared=False)
        cls.stranger_log = create_log(cls.stranger, cls.gym)
        cls.my_log = create_log(cls.me, cls.gym)
        cls.url = reverse("v1:climbs:feed")

    def setUp(self):
        self.client.force_authenticate(self.me)

    def ids(self, response):
        return [item["id"] for item in response.json()["data"]["results"]]

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_explore_returns_shared_logs_newest_first(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.ids(response),
            [self.my_log.id, self.stranger_log.id, self.friend_log.id],
        )

    def test_explore_is_default_scope(self):
        self.assertEqual(
            self.ids(self.client.get(self.url)),
            self.ids(self.client.get(self.url, {"scope": "explore"})),
        )

    def test_invalid_scope_rejected(self):
        self.assertEqual(self.client.get(self.url, {"scope": "x"}).status_code, 400)

    def test_item_shape_and_counts(self):
        ClimbLogLike.objects.create(climb_log=self.friend_log, user=self.me)
        ClimbLogLike.objects.create(climb_log=self.friend_log, user=self.stranger)
        ClimbLogComment.objects.create(
            climb_log=self.friend_log, user=self.me, content="굿"
        )
        ClimbLogComment.objects.create(
            climb_log=self.friend_log, user=self.stranger, content="멋져요"
        )
        # 삭제된 좋아요/댓글은 세지 않는다
        ClimbLogLike.objects.create(
            climb_log=self.friend_log, user=self.friend
        ).delete()

        item = next(
            i
            for i in self.client.get(self.url).json()["data"]["results"]
            if i["id"] == self.friend_log.id
        )
        self.assertEqual(
            set(item),
            {
                "id",
                "user",
                "gym",
                "difficulty",
                "is_success",
                "attempts",
                "memo",
                "video_url",
                "climbed_at",
                "is_shared",
                "like_count",
                "comment_count",
                "is_liked",
                "created_at",
            },
        )
        self.assertEqual(
            item["user"], {"id": self.friend.id, "nickname": "friend", "image": None}
        )
        self.assertEqual(
            item["difficulty"],
            {"id": self.difficulty.id, "name": "초록", "color": "#5f7d4e"},
        )
        self.assertEqual(item["like_count"], 2)
        self.assertEqual(item["comment_count"], 2)
        self.assertTrue(item["is_liked"])

    def test_cursor_pagination(self):
        response = self.client.get(self.url, {"limit": 2})
        data = response.json()["data"]
        self.assertEqual(len(data["results"]), 2)
        self.assertIsNotNone(data["next_cursor"])

        # next_cursor 는 절대 URL — 쿼리 부분만 다시 넣어 다음 페이지 요청
        query = data["next_cursor"].split("?", 1)[1]
        response = self.client.get(f"{self.url}?{query}")
        self.assertEqual(self.ids(response), [self.friend_log.id])

    def test_feed_is_single_query(self):
        for _ in range(3):
            create_log(self.stranger, self.gym, difficulty=self.difficulty)
        ClimbLogLike.objects.create(climb_log=self.stranger_log, user=self.me)
        # 인증은 force_authenticate 라 쿼리 없음 → 목록 1쿼리 (join + annotate)
        with self.assertNumQueries(1):
            response = self.client.get(self.url)
        self.assertEqual(len(response.json()["data"]["results"]), 6)

    def test_following_scope(self):
        Follow = get_follow_model()
        if Follow is None:
            self.skipTest("social.Follow 모델이 아직 없음")
        Follow.objects.create(follower=self.me, following=self.friend)

        response = self.client.get(self.url, {"scope": "following"})
        self.assertEqual(response.status_code, 200)
        # 팔로우한 friend 의 공개 기록만 — 비공개/내 기록/모르는 사람은 제외
        self.assertEqual(self.ids(response), [self.friend_log.id])

    def test_following_scope_without_follows_is_empty(self):
        if get_follow_model() is None:
            self.skipTest("social.Follow 모델이 아직 없음")
        response = self.client.get(self.url, {"scope": "following"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), [])
