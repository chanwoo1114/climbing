"""한국식 비밀번호 규칙 — accounts/validators.py.

프론트 체크리스트(front/src/lib/validation.ts)와 같은 규칙을 서버가 강제한다.
"""

from django.urls import reverse
from rest_framework.test import APITestCase


class PasswordRuleTests(APITestCase):
    url = reverse("v1:auth:register")

    def _register(self, password, seq=0):
        return self.client.post(
            self.url,
            {
                "email": f"rule{seq}@example.com",
                "nickname": f"규칙{seq}",
                "password": password,
            },
        )

    def _error(self, response):
        return response.json()["error"]["fields"]["password"][0]

    # --- 조합 2종 이상 ---

    def test_letters_only_rejected(self):
        response = self._register("azbycxdw", 1)  # 영문만 (연속 아님)
        self.assertEqual(response.status_code, 400)
        self.assertIn("2종류 이상", self._error(response))

    def test_special_only_rejected(self):
        response = self._register("!@#$%^&*", 2)
        self.assertEqual(response.status_code, 400)
        self.assertIn("2종류 이상", self._error(response))

    # --- 연속 문자 ---

    def test_repeated_char_rejected(self):
        response = self._register("s3cure!aaa", 3)
        self.assertEqual(response.status_code, 400)
        self.assertIn("3회 이상 연속", self._error(response))

    def test_ascending_sequence_rejected(self):
        response = self._register("s3cure!123", 4)
        self.assertEqual(response.status_code, 400)
        self.assertIn("연속된 문자", self._error(response))

    def test_alpha_sequence_rejected(self):
        response = self._register("x9!wvuq2", 5)  # wvu 하강 연속
        self.assertEqual(response.status_code, 400)
        self.assertIn("연속된 문자", self._error(response))

    # --- 길이 ---

    def test_seventeen_chars_rejected(self):
        response = self._register("x7q!w9e$r2t5u8o3p", 6)  # 17자
        self.assertEqual(response.status_code, 400)
        self.assertIn("16자", self._error(response))

    def test_sixteen_chars_accepted(self):
        password = "x7q!w9e$r2t5u8o3"  # 정확히 16자
        self.assertEqual(len(password), 16)
        self.assertEqual(self._register(password, 7).status_code, 201)

    # --- 정상 케이스 ---

    def test_valid_passwords_accepted(self):
        for i, password in enumerate(
            ("wall!hold9", "s3cure-pass!", "cr1mp&sloper"), 10
        ):
            with self.subTest(password=password):
                self.assertEqual(self._register(password, i).status_code, 201)
