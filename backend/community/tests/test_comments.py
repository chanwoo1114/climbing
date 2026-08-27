"""게시글 댓글 — 작성/목록(오래된 순), 1단계 답글 제한, 작성자만 삭제(soft delete)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from community.models import PostComment
from community.tests.helpers import create_post


class PostCommentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.post = create_post(cls.author)
        cls.url = reverse("v1:community:post-comments", args=[cls.post.id])

    def setUp(self):
        self.client.force_authenticate(self.user)

    def delete_url(self, comment):
        return reverse(
            "v1:community:post-comment-detail", args=[self.post.id, comment.id]
        )

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

        results = self.client.get(self.url).json()["data"]["results"]
        self.assertEqual([c["content"] for c in results], ["첫 댓글", "둘째 댓글"])

        detail = self.client.get(
            reverse("v1:community:post-detail", args=[self.post.id])
        )
        self.assertEqual(detail.json()["data"]["comment_count"], 2)

    def test_reply_one_level_only(self):
        parent = PostComment.objects.create(
            post=self.post, user=self.author, content="부모"
        )
        reply = self.client.post(self.url, {"content": "답글", "parent": parent.id})
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(reply.json()["data"]["parent"], parent.id)

        nested = self.client.post(
            self.url, {"content": "답글의 답글", "parent": reply.json()["data"]["id"]}
        )
        self.assertEqual(nested.status_code, 400)
        self.assertIn("parent", nested.json()["error"]["fields"])

    def test_reply_to_comment_of_other_post_rejected(self):
        other = create_post(self.author)
        foreign = PostComment.objects.create(post=other, user=self.author, content="x")
        response = self.client.post(self.url, {"content": "답글", "parent": foreign.id})
        self.assertEqual(response.status_code, 400)

    def test_content_validation(self):
        self.assertEqual(self.client.post(self.url, {"content": ""}).status_code, 400)
        self.assertEqual(
            self.client.post(self.url, {"content": "가" * 501}).status_code, 400
        )

    def test_missing_post_404(self):
        url = reverse("v1:community:post-comments", args=[99999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_author_delete_is_soft_with_replies(self):
        comment = PostComment.objects.create(
            post=self.post, user=self.user, content="내 댓글"
        )
        reply = PostComment.objects.create(
            post=self.post, user=self.author, content="답글", parent=comment
        )
        self.assertEqual(self.client.delete(self.delete_url(comment)).status_code, 204)
        self.assertFalse(PostComment.objects.filter(pk=comment.id).exists())
        self.assertTrue(PostComment.all_objects.get(pk=comment.id).is_deleted)
        self.assertFalse(PostComment.objects.filter(pk=reply.id).exists())
        self.assertEqual(len(self.client.get(self.url).json()["data"]["results"]), 0)

    def test_other_cannot_delete(self):
        comment = PostComment.objects.create(
            post=self.post, user=self.author, content="주인 댓글"
        )
        self.assertEqual(self.client.delete(self.delete_url(comment)).status_code, 403)
        self.assertTrue(PostComment.objects.filter(pk=comment.id).exists())
