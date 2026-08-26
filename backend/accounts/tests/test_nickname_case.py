"""닉네임 대소문자 — 표시는 입력한 대로, 중복 판정은 대소문자 무시."""

from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.tests.helpers import PASSWORD, create_verified_user


class NicknameCaseTests(APITestCase):
    register_url = reverse("v1:auth:register")
    me_url = reverse("v1:accounts:me")

    def _register(self, nickname, email="n@example.com"):
        return self.client.post(
            self.register_url,
            {"email": email, "nickname": nickname, "password": PASSWORD},
        )

    def test_nickname_case_is_preserved(self):
        response = self._register("Casey")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["nickname"], "Casey")

    def test_duplicate_differing_only_by_case_rejected(self):
        self.assertEqual(self._register("Casey", "a@example.com").status_code, 201)
        response = self._register("casey", "b@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["fields"]["nickname"],
            ["이미 사용 중인 닉네임입니다."],
        )

    def test_deleted_users_nickname_variant_rejected(self):
        user = User.objects.create_user(
            email="gone@example.com", nickname="탈퇴자Kim", password=PASSWORD
        )
        user.delete()
        self.assertEqual(self._register("탈퇴자kim").status_code, 400)

    def test_profile_update_rejects_case_variant_of_others_nickname(self):
        create_verified_user(email="other@example.com", nickname="Taken")
        me = create_verified_user(email="me@example.com", nickname="원래닉")
        self.client.force_authenticate(me)
        response = self.client.patch(self.me_url, {"nickname": "taken"})
        self.assertEqual(response.status_code, 400)

    def test_profile_update_can_change_own_nickname_case(self):
        # 내 닉네임의 대소문자만 바꾸는 건 중복이 아니다.
        me = create_verified_user(email="me@example.com", nickname="climber")
        self.client.force_authenticate(me)
        response = self.client.patch(self.me_url, {"nickname": "Climber"})
        self.assertEqual(response.status_code, 200)
        me.refresh_from_db()
        self.assertEqual(me.nickname, "Climber")

    def test_db_constraint_blocks_case_duplicate(self):
        User.objects.create_user(
            email="a@example.com", nickname="Race", password=PASSWORD
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            User(email="b@example.com", nickname="rAcE").save()
