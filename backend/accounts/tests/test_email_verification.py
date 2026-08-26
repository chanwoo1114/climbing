"""이메일 인증 — 가입 시 발송, 인증 전 로그인 차단, 토큰 확인, 재전송."""

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.tests.helpers import PASSWORD, extract_query, verify


class EmailVerificationTests(APITestCase):
    register_url = reverse("v1:auth:register")
    login_url = reverse("v1:auth:login")
    verify_url = reverse("v1:auth:verify-email")
    resend_url = reverse("v1:auth:verify-email-resend")

    def _register(self, email="new@example.com", nickname="신규"):
        # register_user 는 커밋 후에 메일을 보낸다 (transaction.on_commit).
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.register_url,
                {"email": email, "nickname": nickname, "password": PASSWORD},
            )
        self.assertEqual(response.status_code, 201)
        return User.objects.get(email=email)

    def _login(self, email="new@example.com"):
        return self.client.post(self.login_url, {"email": email, "password": PASSWORD})

    # --- 발송 ---

    @override_settings(FRONTEND_BASE_URL="https://climb.example")
    def test_register_sends_verification_email_with_frontend_link(self):
        self._register()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["new@example.com"])
        self.assertIn("인증", message.subject)
        self.assertIn("https://climb.example/verify-email?token=", message.body)

    def test_verification_mail_has_html_alternative(self):
        # HTML 본문(디자인 버전)과 텍스트 본문이 같은 링크를 담는다.
        self._register()
        message = mail.outbox[0]
        self.assertEqual(len(message.alternatives), 1)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        token = extract_query(message.body, "token")
        self.assertIn(token, html)
        self.assertIn("이메일 인증하기", html)  # CTA 버튼
        self.assertIn("신규님", html)  # 닉네임 인사
        self.assertNotIn("&amp;", message.body)  # 텍스트 본문은 escape 되면 안 된다
        # 템플릿 주석이 본문으로 새면 doctype 앞에 쓰레기 텍스트가 붙는다.
        self.assertTrue(html.lstrip().lower().startswith("<!doctype html>"), html[:80])
        self.assertNotIn("{#", html)
        self.assertNotIn("{%", html)

    def test_new_user_is_unverified(self):
        user = self._register()
        self.assertIsNone(user.email_verified_at)

    # --- 로그인 차단 ---

    def test_unverified_user_cannot_login(self):
        self._register()
        response = self._login()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "email_not_verified")

    def test_wrong_password_on_unverified_account_is_still_401(self):
        # 미인증 여부보다 비밀번호 검증이 먼저 — 계정 존재가 새지 않는다.
        self._register()
        response = self.client.post(
            self.login_url, {"email": "new@example.com", "password": "wrong-pass!1"}
        )
        self.assertEqual(response.status_code, 401)

    def test_unverified_login_does_not_touch_last_login(self):
        user = self._register()
        self._login()
        user.refresh_from_db()
        self.assertIsNone(user.last_login)

    # --- 토큰 확인 ---

    def test_verify_with_mailed_token_enables_login(self):
        user = self._register()
        token = extract_query(mail.outbox[0].body, "token")

        response = self.client.post(self.verify_url, {"token": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["email"], "new@example.com")

        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(self._login().status_code, 200)

    def test_verify_twice_is_idempotent(self):
        user = self._register()
        token = extract_query(mail.outbox[0].body, "token")
        self.assertEqual(
            self.client.post(self.verify_url, {"token": token}).status_code, 200
        )
        user.refresh_from_db()
        first = user.email_verified_at

        self.assertEqual(
            self.client.post(self.verify_url, {"token": token}).status_code, 200
        )
        user.refresh_from_db()
        self.assertEqual(user.email_verified_at, first)  # 시각이 덮어써지지 않는다

    def test_tampered_token_rejected(self):
        self._register()
        token = extract_query(mail.outbox[0].body, "token")
        response = self.client.post(self.verify_url, {"token": token[:-3] + "xyz"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_token")
        self.assertIsNone(User.objects.get(email="new@example.com").email_verified_at)

    def test_garbage_token_rejected(self):
        response = self.client.post(self.verify_url, {"token": "not-a-token"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_token")

    def test_expired_token_rejected(self):
        self._register()
        token = extract_query(mail.outbox[0].body, "token")
        with override_settings(EMAIL_VERIFICATION_TIMEOUT=-1):
            response = self.client.post(self.verify_url, {"token": token})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_token")

    def test_token_of_deleted_user_rejected(self):
        user = self._register()
        token = extract_query(mail.outbox[0].body, "token")
        user.delete()  # soft delete
        response = self.client.post(self.verify_url, {"token": token})
        self.assertEqual(response.status_code, 400)

    # --- 재전송 ---

    def test_resend_sends_mail_to_unverified_user(self):
        self._register()
        mail.outbox.clear()
        response = self.client.post(self.resend_url, {"email": "new@example.com"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify-email?token=", mail.outbox[0].body)

    def test_resend_ignores_case(self):
        self._register()
        mail.outbox.clear()
        self.client.post(self.resend_url, {"email": "NEW@Example.com"})
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_does_nothing_for_verified_user(self):
        verify(self._register())
        mail.outbox.clear()
        response = self.client.post(self.resend_url, {"email": "new@example.com"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_unknown_email_returns_same_response_without_mail(self):
        # 계정 열거 방지 — 존재하는 이메일과 응답이 같아야 한다.
        response = self.client.post(self.resend_url, {"email": "nobody@example.com"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_rejects_invalid_email_format(self):
        response = self.client.post(self.resend_url, {"email": "not-an-email"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["error"]["fields"])
