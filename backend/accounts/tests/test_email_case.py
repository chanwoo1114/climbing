"""이메일 대소문자 통일.

Django 기본 normalize_email 은 도메인만 소문자화해서 Case@test.com 과
case@test.com 이 별개 계정으로 가입되고, 로그인은 입력한 표기와 정확히
일치할 때만 됐다. 저장은 소문자로 통일하고 중복 검사·로그인은 대소문자를
무시해야 한다.
"""

from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.tests.helpers import verify


class EmailCaseTests(APITestCase):
    register_url = reverse("v1:auth:register")
    login_url = reverse("v1:auth:login")

    def _register(self, email, nickname="케이스"):
        return self.client.post(
            self.register_url,
            {"email": email, "nickname": nickname, "password": "s3cure-pass!"},
        )

    def test_register_stores_lowercase_email(self):
        response = self._register("Case@Test.com")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["email"], "case@test.com")
        self.assertTrue(User.objects.filter(email="case@test.com").exists())

    def test_register_strips_whitespace(self):
        response = self._register("  Spaced@Test.com ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["email"], "spaced@test.com")

    def test_duplicate_email_differing_only_by_case_rejected(self):
        self.assertEqual(self._register("Case@Test.com", "첫째").status_code, 201)
        response = self._register("case@test.com", "둘째")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["fields"]["email"], ["이미 가입된 이메일입니다."]
        )
        self.assertEqual(
            User.all_objects.filter(email__iexact="case@test.com").count(), 1
        )

    def test_uppercase_variant_of_deleted_email_rejected(self):
        # 탈퇴 계정도 대소문자 무시로 중복 검사된다.
        user = User.objects.create_user(
            email="gone@test.com", nickname="탈퇴", password="s3cure-pass!"
        )
        user.delete()
        response = self._register("GONE@test.com", "재가입")
        self.assertEqual(response.status_code, 400)

    def test_login_ignores_case(self):
        self._register("Case@Test.com")
        verify(User.objects.get(email="case@test.com"))
        for typed in ("case@test.com", "CASE@TEST.COM", "Case@Test.com"):
            with self.subTest(typed=typed):
                response = self.client.post(
                    self.login_url, {"email": typed, "password": "s3cure-pass!"}
                )
                self.assertEqual(response.status_code, 200)

    def test_manager_create_user_lowercases(self):
        # 시리얼라이저를 거치지 않는 경로(쉘·관리자·픽스처)도 동일하게 정규화된다.
        user = User.objects.create_user(
            email="Shell@Test.com", nickname="쉘", password="s3cure-pass!"
        )
        self.assertEqual(user.email, "shell@test.com")

    def test_db_constraint_blocks_case_duplicate(self):
        # 시리얼라이저 검사를 우회해도 DB 가 막는다 (동시 가입 경합 대비).
        User.objects.create_user(
            email="race@test.com", nickname="레이스1", password="s3cure-pass!"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            User(email="Race@test.com", nickname="레이스2").save()
