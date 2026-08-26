"""공개 인증 엔드포인트 rate limit.

테스트 설정은 DummyCache 라 throttle 이 꺼져 있다 (다른 테스트가 로그인을 여러 번
해도 429 가 안 나게). 여기서만 LocMem 으로 바꿔 실제 카운팅을 검증한다.
"""

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import PASSWORD, create_verified_user

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class ThrottleTests(APITestCase):
    login_url = reverse("v1:auth:login")
    register_url = reverse("v1:auth:register")
    resend_url = reverse("v1:auth:verify-email-resend")
    reset_url = reverse("v1:auth:password-reset")

    def setUp(self):
        cache.clear()
        create_verified_user(email="limit@example.com", nickname="한도")

    def _login(self, password="wrong-pass!1"):
        return self.client.post(
            self.login_url, {"email": "limit@example.com", "password": password}
        )

    def _register(self, seq):
        return self.client.post(
            self.register_url,
            {
                "email": f"r{seq}@example.com",
                "nickname": f"봇{seq}",
                "password": PASSWORD,
            },
        )

    def test_login_blocked_after_5_attempts_per_minute(self):
        for _ in range(5):
            self.assertEqual(self._login().status_code, 401)
        response = self._login()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "throttled")
        self.assertIn("Retry-After", response.headers)

    def test_correct_password_is_also_blocked_once_limited(self):
        # 한도는 성공/실패를 가리지 않는다 — 공격자가 맞는 비밀번호를 찾아도 막힌다.
        for _ in range(5):
            self._login()
        self.assertEqual(self._login(PASSWORD).status_code, 429)

    def test_register_blocked_after_5_per_hour(self):
        for i in range(5):
            self.assertEqual(self._register(i).status_code, 201)
        self.assertEqual(self._register(99).status_code, 429)

    def test_scopes_are_independent(self):
        # 로그인 한도를 다 써도 가입은 된다 (scope 분리).
        for _ in range(6):
            self._login()
        self.assertEqual(self._register(1).status_code, 201)

    def test_email_send_endpoints_share_one_limit(self):
        # 재전송 + 재설정 요청이 같은 scope(email_send) 를 쓴다 — 메일 폭탄 방지.
        for _ in range(3):
            self.assertEqual(
                self.client.post(
                    self.resend_url, {"email": "x@example.com"}
                ).status_code,
                202,
            )
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    self.reset_url, {"email": "x@example.com"}
                ).status_code,
                202,
            )
        self.assertEqual(
            self.client.post(self.reset_url, {"email": "x@example.com"}).status_code,
            429,
        )

    def test_throttle_response_uses_envelope(self):
        for _ in range(6):
            response = self._login()
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIsNone(body["data"])
        # 한국어 한 문장 + 대기 시간 (Retry-After 와 같은 값)
        self.assertRegex(body["error"]["message"], r"^요청이 너무 많습니다\. \d+초 후")
        self.assertIn(response.headers["Retry-After"], body["error"]["message"])
