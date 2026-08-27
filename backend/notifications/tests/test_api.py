"""알림 REST — 목록(커서/unread 필터), 미읽음 수, 읽음/전체 읽음, 삭제, 401, 남의 알림 404."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from notifications.models import Notification
from notifications.tests.helpers import create_notification


class NotificationApiBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="a@example.com", nickname="alpha")
        cls.actor = create_verified_user(email="b@example.com", nickname="bravo")
        cls.other = create_verified_user(email="c@example.com", nickname="charlie")

    def setUp(self):
        self.older = create_notification(
            self.me, self.actor, type="like", target_type="climb_log", target_id=7
        )
        self.read = create_notification(self.me, None, message="시스템", is_read=True)
        self.newest = create_notification(self.me, self.actor, type="follow")
        self.theirs = create_notification(self.other, self.actor)
        self.client.force_authenticate(self.me)

    def list_url(self):
        return reverse("v1:notifications:list")


class NotificationListTests(NotificationApiBase):
    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url()).status_code, 401)
        url = reverse("v1:notifications:unread-count")
        self.assertEqual(self.client.get(url).status_code, 401)

    def test_lists_only_mine_newest_first_with_envelope(self):
        res = self.client.get(self.list_url())
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIn("next_cursor", body["data"])
        results = body["data"]["results"]
        self.assertEqual(
            [r["id"] for r in results], [self.newest.id, self.read.id, self.older.id]
        )

        like = results[-1]
        self.assertEqual(like["type"], "like")
        self.assertEqual(
            like["actor"], {"id": self.actor.id, "nickname": "bravo", "image": None}
        )
        self.assertEqual(like["target_type"], "climb_log")
        self.assertEqual(like["target_id"], 7)
        self.assertFalse(like["is_read"])
        self.assertIn("created_at", like)

        system = results[1]
        self.assertIsNone(system["actor"])
        self.assertTrue(system["is_read"])

    def test_unread_filter(self):
        res = self.client.get(self.list_url(), {"unread": "true"})
        ids = [r["id"] for r in res.json()["data"]["results"]]
        self.assertEqual(ids, [self.newest.id, self.older.id])

    def test_cursor_pagination(self):
        first = self.client.get(self.list_url(), {"limit": 2}).json()["data"]
        self.assertEqual(len(first["results"]), 2)
        self.assertIsNotNone(first["next_cursor"])
        second = self.client.get(first["next_cursor"]).json()["data"]
        self.assertEqual([r["id"] for r in second["results"]], [self.older.id])

    def test_deleted_notifications_are_hidden(self):
        self.older.delete()
        ids = [
            r["id"] for r in self.client.get(self.list_url()).json()["data"]["results"]
        ]
        self.assertNotIn(self.older.id, ids)


class UnreadCountTests(NotificationApiBase):
    def test_counts_unread_of_mine(self):
        res = self.client.get(reverse("v1:notifications:unread-count"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"], {"count": 2})


class MarkReadTests(NotificationApiBase):
    def test_read_marks_and_returns_item(self):
        url = reverse("v1:notifications:read", args=[self.older.id])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["data"]["is_read"])
        self.older.refresh_from_db()
        self.assertTrue(self.older.is_read)
        self.assertIsNotNone(self.older.read_at)

        first_read_at = self.older.read_at
        self.assertEqual(self.client.post(url).status_code, 200)  # 멱등
        self.older.refresh_from_db()
        self.assertEqual(self.older.read_at, first_read_at)

        count = self.client.get(reverse("v1:notifications:unread-count")).json()
        self.assertEqual(count["data"]["count"], 1)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        url = reverse("v1:notifications:read", args=[self.older.id])
        self.assertEqual(self.client.post(url).status_code, 401)

    def test_other_users_notification_is_404(self):
        url = reverse("v1:notifications:read", args=[self.theirs.id])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.theirs.refresh_from_db()
        self.assertFalse(self.theirs.is_read)

    def test_read_all(self):
        url = reverse("v1:notifications:read-all")
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"], {"updated": 2})
        self.assertEqual(
            Notification.objects.filter(recipient=self.me, is_read=False).count(), 0
        )
        self.assertEqual(self.client.post(url).json()["data"], {"updated": 0})
        self.theirs.refresh_from_db()
        self.assertFalse(self.theirs.is_read)  # 남의 것은 그대로

    def test_read_all_requires_auth(self):
        self.client.force_authenticate(None)
        url = reverse("v1:notifications:read-all")
        self.assertEqual(self.client.post(url).status_code, 401)


class DeleteTests(NotificationApiBase):
    def test_soft_deletes_mine(self):
        url = reverse("v1:notifications:detail", args=[self.older.id])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Notification.objects.filter(pk=self.older.id).exists())
        gone = Notification.all_objects.get(pk=self.older.id)
        self.assertTrue(gone.is_deleted)
        self.assertIsNotNone(gone.deleted_at)
        self.assertEqual(self.client.delete(url).status_code, 404)  # 이미 삭제됨

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        url = reverse("v1:notifications:detail", args=[self.older.id])
        self.assertEqual(self.client.delete(url).status_code, 401)

    def test_other_users_notification_is_404(self):
        url = reverse("v1:notifications:detail", args=[self.theirs.id])
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Notification.objects.filter(pk=self.theirs.id).exists())
