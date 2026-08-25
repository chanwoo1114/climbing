"""탈퇴(soft delete) 계정 처리.

User.objects 가 is_deleted 를 걸러내지 않으면 탈퇴 계정으로 로그인이 되고,
반대로 중복 검사를 objects 로 하면 DB UNIQUE 제약과 어긋나 500이 난다.
"""

from django.contrib.auth import authenticate
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User


class SoftDeletedUserTests(APITestCase):
    login_url = reverse("v1:auth:login")
    register_url = reverse("v1:auth:register")

    def setUp(self):
        self.user = User.objects.create_user(
            email="gone@example.com", nickname="탈퇴자", password="s3cure-pass!"
        )
        self.user.delete()  # soft delete

    def test_default_manager_excludes_deleted(self):
        self.assertEqual(User.objects.filter(email="gone@example.com").count(), 0)
        self.assertEqual(User.all_objects.filter(email="gone@example.com").count(), 1)

    def test_default_manager_is_objects(self):
        # authenticate() 가 _default_manager 를 쓰기 때문에 고정되어야 한다.
        self.assertIs(User._default_manager, User.objects)

    def test_deleted_user_cannot_authenticate(self):
        self.assertIsNone(
            authenticate(email="gone@example.com", password="s3cure-pass!")
        )

    def test_deleted_user_cannot_login_via_api(self):
        response = self.client.post(
            self.login_url,
            {"email": "gone@example.com", "password": "s3cure-pass!"},
        )
        self.assertEqual(response.status_code, 401)

    def test_deleted_email_cannot_be_reused(self):
        # DB UNIQUE 는 is_deleted 를 구분하지 않으므로 400으로 막아야 한다 (500 아님).
        response = self.client.post(
            self.register_url,
            {
                "email": "gone@example.com",
                "nickname": "재가입시도",
                "password": "s3cure-pass!",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["fields"]["email"], ["이미 가입된 이메일입니다."]
        )

    def test_deleted_nickname_cannot_be_reused(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "new@example.com",
                "nickname": "탈퇴자",
                "password": "s3cure-pass!",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["fields"]["nickname"],
            ["이미 사용 중인 닉네임입니다."],
        )

    def test_active_user_unaffected(self):
        User.objects.create_user(
            email="alive@example.com", nickname="현역", password="s3cure-pass!"
        )
        response = self.client.post(
            self.login_url,
            {"email": "alive@example.com", "password": "s3cure-pass!"},
        )
        self.assertEqual(response.status_code, 200)
