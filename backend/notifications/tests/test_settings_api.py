"""알림 채널 설정 REST — GET 기본값(행 자동 생성), PATCH(부분 갱신), 401."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from notifications.models import NotificationSetting


class NotificationSettingApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="a@example.com", nickname="alpha")
        cls.url = reverse("v1:notifications:settings")

    def setUp(self):
        self.client.force_authenticate(self.me)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(
            self.client.patch(self.url, {"push_enabled": False}).status_code, 401
        )

    def test_get_creates_default_row(self):
        self.assertFalse(NotificationSetting.objects.filter(user=self.me).exists())
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"], {"push_enabled": True, "email_enabled": True})
        self.assertEqual(NotificationSetting.objects.filter(user=self.me).count(), 1)

        self.client.get(self.url)  # 두 번째 호출은 새 행을 만들지 않는다
        self.assertEqual(NotificationSetting.objects.filter(user=self.me).count(), 1)

    def test_patch_single_field_keeps_the_other(self):
        res = self.client.patch(self.url, {"push_enabled": False}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()["data"], {"push_enabled": False, "email_enabled": True}
        )
        setting = NotificationSetting.objects.get(user=self.me)
        self.assertFalse(setting.push_enabled)
        self.assertTrue(setting.email_enabled)

        res = self.client.patch(self.url, {"email_enabled": False}, format="json")
        self.assertEqual(
            res.json()["data"], {"push_enabled": False, "email_enabled": False}
        )

    def test_patch_both_fields(self):
        res = self.client.patch(
            self.url, {"push_enabled": False, "email_enabled": False}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()["data"], {"push_enabled": False, "email_enabled": False}
        )

    def test_patch_rejects_non_boolean(self):
        res = self.client.patch(self.url, {"push_enabled": "maybe"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])
