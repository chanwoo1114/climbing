"""댓글 — 작성/목록(오래된 순), 1단계 답글 제한, 작성자만 삭제(soft delete)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.models import ClimbLogComment
from climbs.tests.helpers import create_gym, create_log


class ClimbLogCommentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym)
        cls.private = create_log(cls.owner, cls.gym, is_shared=False)
        cls.url = reverse("v1:climbs:log-comments", args=[cls.log.id])

    def setUp(self):
        self.client.force_authenticate(self.user)

    def delete_url(self, comment):
        return reverse("v1:climbs:log-comment-detail", args=[self.log.id, comment.id])

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url, {"content": "x"}).status_code, 401)

    def test_create_and_list_oldest_first(self):
        first = self.client.post(self.url, {"content": "첫 댓글"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["data"]["user"]["nickname"], "bravo")
        self.assertIsNone(first.json()["data"]["parent"])
        self.client.post(self.url, {"content": "둘째 댓글"})

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual([c["content"] for c in results], ["첫 댓글", "둘째 댓글"])

        detail = self.client.get(reverse("v1:climbs:log-detail", args=[self.log.id]))
        self.assertEqual(detail.json()["data"]["comment_count"], 2)

    def test_reply_one_level_only(self):
        parent = ClimbLogComment.objects.create(
            climb_log=self.log, user=self.owner, content="부모"
        )
        reply = self.client.post(self.url, {"content": "답글", "parent": parent.id})
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(reply.json()["data"]["parent"], parent.id)

        nested = self.client.post(
            self.url, {"content": "답글의 답글", "parent": reply.json()["data"]["id"]}
        )
        self.assertEqual(nested.status_code, 400)
        self.assertIn("parent", nested.json()["error"]["fields"])

    def test_reply_to_comment_of_other_log_rejected(self):
        other_log = create_log(self.owner, self.gym)
        foreign = ClimbLogComment.objects.create(
            climb_log=other_log, user=self.owner, content="다른 기록 댓글"
        )
        response = self.client.post(self.url, {"content": "답글", "parent": foreign.id})
        self.assertEqual(response.status_code, 400)

    def test_content_validation(self):
        self.assertEqual(self.client.post(self.url, {"content": ""}).status_code, 400)
        self.assertEqual(
            self.client.post(self.url, {"content": "가" * 501}).status_code, 400
        )

    def test_private_log_of_other_is_hidden(self):
        url = reverse("v1:climbs:log-comments", args=[self.private.id])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"content": "x"}).status_code, 404)

    def test_author_delete_is_soft(self):
        comment = ClimbLogComment.objects.create(
            climb_log=self.log, user=self.user, content="내 댓글"
        )
        response = self.client.delete(self.delete_url(comment))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ClimbLogComment.objects.filter(pk=comment.id).exists())
        self.assertTrue(ClimbLogComment.all_objects.get(pk=comment.id).is_deleted)
        self.assertEqual(len(self.client.get(self.url).json()["data"]["results"]), 0)

    def test_other_cannot_delete(self):
        comment = ClimbLogComment.objects.create(
            climb_log=self.log, user=self.owner, content="주인 댓글"
        )
        self.assertEqual(self.client.delete(self.delete_url(comment)).status_code, 403)
        self.assertTrue(ClimbLogComment.objects.filter(pk=comment.id).exists())

    def test_delete_missing_comment_404(self):
        url = reverse("v1:climbs:log-comment-detail", args=[self.log.id, 99999])
        self.assertEqual(self.client.delete(url).status_code, 404)
