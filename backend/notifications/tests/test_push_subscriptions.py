"""Web Push 구독 REST.

공개키(200/503), 등록 201 + endpoint upsert/이관, 400, 해지 204(멱등·본인만), 401.
"""

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from notifications.models import PushSubscription

VAPID = {
    "WEBPUSH_VAPID_PUBLIC_KEY": "test-public-key",
    "WEBPUSH_VAPID_PRIVATE_KEY": "test-private-key",
}
NO_VAPID = {"WEBPUSH_VAPID_PUBLIC_KEY": "", "WEBPUSH_VAPID_PRIVATE_KEY": ""}

ENDPOINT = "https://push.example.com/send/abc123"


def subscribe_body(endpoint=ENDPOINT, p256dh="p256dh-key", auth="auth-secret", **extra):
    body = {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
    body.update(extra)
    return body


class PushApiBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="a@example.com", nickname="alpha")
        cls.other = create_verified_user(email="b@example.com", nickname="bravo")
        cls.key_url = reverse("v1:notifications:push-public-key")
        cls.sub_url = reverse("v1:notifications:push-subscriptions")

    def setUp(self):
        self.client.force_authenticate(self.me)


@override_settings(**VAPID)
class PushPublicKeyTests(PushApiBase):
    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.key_url).status_code, 401)

    def test_returns_public_key(self):
        res = self.client.get(self.key_url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"], {"public_key": "test-public-key"})

    @override_settings(**NO_VAPID)
    def test_503_when_not_configured(self):
        res = self.client.get(self.key_url)
        self.assertEqual(res.status_code, 503)
        body = res.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "push_not_configured")


@override_settings(**VAPID)
class PushSubscribeTests(PushApiBase):
    def test_requires_auth(self):
        self.client.force_authenticate(None)
        res = self.client.post(self.sub_url, subscribe_body(), format="json")
        self.assertEqual(res.status_code, 401)

    def test_subscribe_creates_row(self):
        res = self.client.post(
            self.sub_url, subscribe_body(user_agent="Chrome/130"), format="json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertEqual(set(data), {"id", "endpoint", "created_at"})
        self.assertEqual(data["endpoint"], ENDPOINT)

        sub = PushSubscription.objects.get(pk=data["id"])
        self.assertEqual(sub.user_id, self.me.id)
        self.assertEqual((sub.p256dh, sub.auth), ("p256dh-key", "auth-secret"))
        self.assertEqual(sub.user_agent, "Chrome/130")
        self.assertIsNone(sub.last_used_at)

    def test_resubscribe_same_endpoint_updates_keys_in_place(self):
        first = self.client.post(self.sub_url, subscribe_body(), format="json")
        second = self.client.post(
            self.sub_url,
            subscribe_body(p256dh="new-key", auth="new-auth"),
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["data"]["id"], second.json()["data"]["id"])
        self.assertEqual(PushSubscription.objects.count(), 1)
        sub = PushSubscription.objects.get()
        self.assertEqual((sub.p256dh, sub.auth), ("new-key", "new-auth"))

    def test_same_endpoint_by_another_user_is_reassigned(self):
        """같은 브라우저에서 다른 계정으로 로그인해 구독하면 구독이 그 계정으로 넘어간다."""
        mine = self.client.post(self.sub_url, subscribe_body(), format="json")
        self.client.force_authenticate(self.other)
        theirs = self.client.post(self.sub_url, subscribe_body(), format="json")

        self.assertEqual(theirs.status_code, 201)
        self.assertEqual(mine.json()["data"]["id"], theirs.json()["data"]["id"])
        self.assertEqual(PushSubscription.objects.count(), 1)
        self.assertEqual(PushSubscription.objects.get().user_id, self.other.id)
        self.assertFalse(PushSubscription.objects.filter(user=self.me).exists())

    def test_long_user_agent_is_truncated_not_rejected(self):
        res = self.client.post(
            self.sub_url, subscribe_body(user_agent="x" * 600), format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(PushSubscription.objects.get().user_agent), 255)

    def test_rejects_non_https_endpoint(self):
        res = self.client.post(
            self.sub_url,
            subscribe_body(endpoint="http://push.example.com/send/abc"),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("endpoint", res.json()["error"]["fields"])

    def test_rejects_missing_keys(self):
        res = self.client.post(self.sub_url, {"endpoint": ENDPOINT}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            self.sub_url,
            {"endpoint": ENDPOINT, "keys": {"p256dh": "only"}},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(PushSubscription.objects.count(), 0)

    @override_settings(**NO_VAPID)
    def test_503_when_not_configured(self):
        res = self.client.post(self.sub_url, subscribe_body(), format="json")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["error"]["code"], "push_not_configured")
        self.assertEqual(PushSubscription.objects.count(), 0)


@override_settings(**VAPID)
class PushUnsubscribeTests(PushApiBase):
    def setUp(self):
        super().setUp()
        self.mine = PushSubscription.objects.create(
            user=self.me, endpoint=ENDPOINT, p256dh="k", auth="a"
        )
        self.theirs = PushSubscription.objects.create(
            user=self.other,
            endpoint="https://push.example.com/send/theirs",
            p256dh="k",
            auth="a",
        )

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        res = self.client.delete(self.sub_url, {"endpoint": ENDPOINT}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_delete_removes_own_row_and_is_idempotent(self):
        res = self.client.delete(self.sub_url, {"endpoint": ENDPOINT}, format="json")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(PushSubscription.all_objects.filter(pk=self.mine.pk).exists())

        res = self.client.delete(self.sub_url, {"endpoint": ENDPOINT}, format="json")
        self.assertEqual(res.status_code, 204)

    def test_delete_does_not_touch_other_users_row(self):
        res = self.client.delete(
            self.sub_url, {"endpoint": self.theirs.endpoint}, format="json"
        )
        self.assertEqual(res.status_code, 204)
        self.assertTrue(PushSubscription.objects.filter(pk=self.theirs.pk).exists())

    def test_delete_requires_endpoint(self):
        res = self.client.delete(self.sub_url, {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_can_resubscribe_after_delete(self):
        self.client.delete(self.sub_url, {"endpoint": ENDPOINT}, format="json")
        res = self.client.post(self.sub_url, subscribe_body(), format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(PushSubscription.objects.filter(user=self.me).count(), 1)
