"""로그인 상태 비밀번호 변경 — auth/password/change/.

현재 비밀번호 확인 → 새 비밀번호 규칙(가입과 동일) → 기존 refresh 전부 블랙리스트 →
새 토큰 쌍 반환. 소셜 전용 계정(비밀번호 없음)은 400 no_password.
"""

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.tests.helpers import PASSWORD, create_verified_user

NEW_PASSWORD = "n3w-pass!ok"


class PasswordChangeTests(APITestCase):
    url = reverse("v1:auth:password-change")
    refresh_url = reverse("v1:auth:refresh")
    login_url = reverse("v1:auth:login")

    def setUp(self):
        self.user = create_verified_user(email="pw@example.com", nickname="pwuser")
        self.client.force_authenticate(self.user)

    def _change(self, current=PASSWORD, new=NEW_PASSWORD):
        return self.client.post(
            self.url, {"current_password": current, "new_password": new}
        )

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self._change().status_code, 401)

    def test_changes_password_and_returns_new_tokens(self):
        response = self._change()
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("access", data)
        self.assertIn("refresh", data)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(PASSWORD))

        # 새 refresh 는 바로 쓸 수 있다
        self.client.force_authenticate(None)
        refreshed = self.client.post(self.refresh_url, {"refresh": data["refresh"]})
        self.assertEqual(refreshed.status_code, 200)

    def test_old_refresh_tokens_are_blacklisted(self):
        old_refresh = str(RefreshToken.for_user(self.user))
        self.assertEqual(self._change().status_code, 200)

        self.client.force_authenticate(None)
        response = self.client.post(self.refresh_url, {"refresh": old_refresh})
        self.assertEqual(response.status_code, 401)

    def test_login_with_new_password(self):
        self.assertEqual(self._change().status_code, 200)
        self.client.force_authenticate(None)
        ok = self.client.post(
            self.login_url, {"email": "pw@example.com", "password": NEW_PASSWORD}
        )
        self.assertEqual(ok.status_code, 200)
        bad = self.client.post(
            self.login_url, {"email": "pw@example.com", "password": PASSWORD}
        )
        self.assertEqual(bad.status_code, 401)

    def test_wrong_current_password(self):
        response = self._change(current="wrong-pass!1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.json()["error"]["fields"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_same_password_rejected(self):
        response = self._change(new=PASSWORD)
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json()["error"]["fields"])

    def test_new_password_follows_signup_rules(self):
        # 영문만 (조합 2종 미만) — accounts/validators.py 규칙
        response = self._change(new="azbycxdw")
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json()["error"]["fields"])

    def test_new_password_must_not_contain_nickname(self):
        response = self._change(new="pwuser!1x")
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json()["error"]["fields"])

    def test_missing_fields(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)
        fields = response.json()["error"]["fields"]
        self.assertIn("current_password", fields)
        self.assertIn("new_password", fields)

    def test_social_only_account_has_no_password(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        response = self._change()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "no_password")
