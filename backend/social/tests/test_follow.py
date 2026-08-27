from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from social.models import Follow


class FollowTests(APITestCase):
    def setUp(self):
        self.me = create_verified_user(email="me@example.com", nickname="me")
        self.other = create_verified_user(email="other@example.com", nickname="other")
        self.client.force_authenticate(self.me)

    def url(self, user_id):
        return reverse("v1:social:follow", kwargs={"pk": user_id})

    def test_follow_creates_relation(self):
        response = self.client.post(self.url(self.other.pk))
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Follow.objects.filter(follower=self.me, following=self.other).exists()
        )

    def test_follow_is_idempotent(self):
        self.client.post(self.url(self.other.pk))
        response = self.client.post(self.url(self.other.pk))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Follow.all_objects.count(), 1)

    def test_cannot_follow_self(self):
        response = self.client.post(self.url(self.me.pk))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "self_follow")
        self.assertFalse(Follow.all_objects.exists())

    def test_follow_unknown_user_404(self):
        response = self.client.post(self.url(99999))
        self.assertEqual(response.status_code, 404)

    def test_follow_soft_deleted_user_404(self):
        self.other.delete()
        response = self.client.post(self.url(self.other.pk))
        self.assertEqual(response.status_code, 404)

    def test_unfollow_removes_relation(self):
        self.client.post(self.url(self.other.pk))
        response = self.client.delete(self.url(self.other.pk))
        self.assertEqual(response.status_code, 204)
        # hard delete — 소프트 삭제 행도 남지 않는다.
        self.assertFalse(Follow.all_objects.exists())

    def test_unfollow_when_not_following_is_noop(self):
        response = self.client.delete(self.url(self.other.pk))
        self.assertEqual(response.status_code, 204)

    def test_unfollow_unknown_user_404(self):
        response = self.client.delete(self.url(99999))
        self.assertEqual(response.status_code, 404)

    def test_follow_unfollow_follow_sequence(self):
        self.assertEqual(self.client.post(self.url(self.other.pk)).status_code, 201)
        self.assertEqual(self.client.delete(self.url(self.other.pk)).status_code, 204)
        self.assertEqual(self.client.post(self.url(self.other.pk)).status_code, 201)
        self.assertEqual(
            Follow.objects.filter(follower=self.me, following=self.other).count(), 1
        )

    def test_refollow_restores_soft_deleted_row(self):
        # admin 등에서 soft delete 된 행이 남아 있어도 UNIQUE 에 걸리지 않는다.
        Follow.objects.create(follower=self.me, following=self.other).delete()
        self.assertFalse(Follow.objects.exists())
        response = self.client.post(self.url(self.other.pk))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Follow.all_objects.count(), 1)
        self.assertTrue(
            Follow.objects.filter(follower=self.me, following=self.other).exists()
        )

    def test_unfollow_does_not_touch_reverse_relation(self):
        Follow.objects.create(follower=self.other, following=self.me)
        self.client.post(self.url(self.other.pk))
        self.client.delete(self.url(self.other.pk))
        self.assertTrue(
            Follow.objects.filter(follower=self.other, following=self.me).exists()
        )

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.url(self.other.pk)).status_code, 401)
        self.assertEqual(self.client.delete(self.url(self.other.pk)).status_code, 401)
