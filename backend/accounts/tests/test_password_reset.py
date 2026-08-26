"""비밀번호 재설정 — 요청 메일, 토큰 확인, 1회성, 세션 무효화."""

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.services import register_user
from accounts.tests.helpers import PASSWORD, create_verified_user, extract_query

NEW_PASSWORD = "n3w-pass!ok"


class PasswordResetTests(APITestCase):
    request_url = reverse("v1:auth:password-reset")
    confirm_url = reverse("v1:auth:password-reset-confirm")
    login_url = reverse("v1:auth:login")
    refresh_url = reverse("v1:auth:refresh")

    def setUp(self):
        self.user = create_verified_user(email="reset@example.com", nickname="리셋")

    def _request(self, email="reset@example.com"):
        return self.client.post(self.request_url, {"email": email})

    def _credentials(self):
        """메일 본문에서 (uid, token) 추출."""
        body = mail.outbox[-1].body
        return extract_query(body, "uid"), extract_query(body, "token")

    def _confirm(self, uid, token, password=NEW_PASSWORD):
        return self.client.post(
            self.confirm_url, {"uid": uid, "token": token, "password": password}
        )

    def _login(self, password):
        return self.client.post(
            self.login_url, {"email": "reset@example.com", "password": password}
        )

    # --- 요청 ---

    @override_settings(FRONTEND_BASE_URL="https://climb.example")
    def test_request_sends_mail_with_reset_link(self):
        response = self._request()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["reset@example.com"])
        self.assertIn("https://climb.example/reset-password?uid=", mail.outbox[0].body)
        self.assertIn("&token=", mail.outbox[0].body)

    def test_reset_mail_has_html_alternative(self):
        self._request()
        message = mail.outbox[0]
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        uid, token = self._credentials()
        # HTML 안에서는 & 가 &amp; 로 escape 된 채 링크가 살아 있어야 한다.
        self.assertIn(f"uid={uid}&amp;token={token}", html)
        self.assertIn("새 비밀번호 설정하기", html)
        self.assertNotIn("&amp;", message.body)

    def test_request_ignores_case(self):
        self._request("RESET@Example.com")
        self.assertEqual(len(mail.outbox), 1)

    def test_request_unknown_email_same_response_without_mail(self):
        response = self._request("nobody@example.com")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 0)

    def test_request_for_deleted_user_sends_nothing(self):
        self.user.delete()
        self.assertEqual(self._request().status_code, 202)
        self.assertEqual(len(mail.outbox), 0)

    # --- 확정 ---

    def test_confirm_sets_new_password(self):
        self._request()
        uid, token = self._credentials()
        self.assertEqual(self._confirm(uid, token).status_code, 204)
        self.assertEqual(self._login(NEW_PASSWORD).status_code, 200)
        self.assertEqual(self._login(PASSWORD).status_code, 401)

    def test_token_is_single_use(self):
        self._request()
        uid, token = self._credentials()
        self.assertEqual(self._confirm(uid, token).status_code, 204)
        response = self._confirm(uid, token, "an0ther-pass!")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_token")
        # 두 번째 시도는 비밀번호를 바꾸지 못한다.
        self.assertEqual(self._login(NEW_PASSWORD).status_code, 200)

    def test_tampered_token_rejected(self):
        self._request()
        uid, token = self._credentials()
        response = self._confirm(uid, token[:-2] + "zz")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_token")
        self.assertEqual(self._login(PASSWORD).status_code, 200)  # 그대로

    def test_bad_uid_rejected(self):
        self._request()
        _, token = self._credentials()
        self.assertEqual(self._confirm("not-base64!", token).status_code, 400)
        self.assertEqual(self._confirm("OTk5OTk", token).status_code, 400)  # 없는 pk

    def test_weak_password_rejected_with_field_error(self):
        self._request()
        uid, token = self._credentials()
        response = self._confirm(uid, token, "12345678")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])
        # 규칙 위반 시 토큰은 소모되지 않는다 — 다시 시도 가능.
        self.assertEqual(self._confirm(uid, token).status_code, 204)

    def test_password_similar_to_email_rejected(self):
        # 유사도 검사에 user 가 전달되어야 걸린다.
        self._request()
        uid, token = self._credentials()
        response = self._confirm(uid, token, "reset@example")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])

    def test_confirm_invalidates_existing_refresh_tokens(self):
        # 다른 기기에 남아있던 세션은 재설정과 함께 끊긴다.
        old_refresh = self._login(PASSWORD).json()["data"]["refresh"]
        self._request()
        uid, token = self._credentials()
        self.assertEqual(self._confirm(uid, token).status_code, 204)
        response = self.client.post(self.refresh_url, {"refresh": old_refresh})
        self.assertEqual(response.status_code, 401)

    def test_confirm_marks_unverified_user_as_verified(self):
        # 재설정 링크를 열었다는 건 메일 소유 증명이다.
        register_user(email="fresh@example.com", nickname="미인증", password=PASSWORD)
        self.assertIsNone(User.objects.get(email="fresh@example.com").email_verified_at)
        self._request("fresh@example.com")
        uid, token = self._credentials()
        self.assertEqual(self._confirm(uid, token).status_code, 204)
        self.assertIsNotNone(
            User.objects.get(email="fresh@example.com").email_verified_at
        )
        response = self.client.post(
            self.login_url, {"email": "fresh@example.com", "password": NEW_PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
