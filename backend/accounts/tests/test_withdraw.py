"""회원 탈퇴 — DELETE users/me/.

비밀번호 재확인(소셜 전용 계정은 생략) → 크루장이면 409 → 크루 탈퇴 → refresh 블랙리스트
→ 이메일·닉네임 자리표시자로 교체 + is_active=False → soft delete(cascade).
"""

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import SocialAccount, User, UserProfile
from accounts.services import withdrawn_email, withdrawn_nickname
from accounts.tests.helpers import PASSWORD, create_verified_user
from chat.models import ChatRoomMember, Message
from climbs.models import ClimbLog
from climbs.tests.helpers import create_gym, create_log
from crews.models import CrewMember
from crews.tests.helpers import add_member, create_crew
from social.models import Follow
from social.services import follow_user


class WithdrawTests(APITestCase):
    url = reverse("v1:accounts:me")
    refresh_url = reverse("v1:auth:refresh")
    register_url = reverse("v1:auth:register")

    def setUp(self):
        self.user = create_verified_user(email="bye@example.com", nickname="bye")
        self.other = create_verified_user(email="stay@example.com", nickname="stay")
        self.client.force_authenticate(self.user)

    def _withdraw(self, password=PASSWORD):
        return self.client.delete(self.url, {"password": password})

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self._withdraw().status_code, 401)

    def test_requires_password(self):
        response = self.client.delete(self.url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_password(self):
        response = self._withdraw("wrong-pass!1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_withdraw_soft_deletes_and_anonymizes(self):
        response = self._withdraw()
        self.assertEqual(response.status_code, 204)

        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        user = User.all_objects.get(pk=self.user.pk)
        self.assertTrue(user.is_deleted)
        self.assertIsNotNone(user.deleted_at)
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.email, withdrawn_email(user.pk))
        self.assertEqual(user.nickname, withdrawn_nickname(user.pk))
        # 프로필도 cascade soft delete
        self.assertFalse(UserProfile.objects.filter(user=user).exists())

    def test_withdraw_cascades_logs_follows_and_social_accounts(self):
        gym = create_gym()
        log = create_log(self.user, gym)
        follow_user(follower=self.user, target_id=self.other.id)
        follow_user(follower=self.other, target_id=self.user.id)
        SocialAccount.objects.create(
            user=self.user, provider="kakao", provider_uid="k-1"
        )

        self.assertEqual(self._withdraw().status_code, 204)

        self.assertFalse(ClimbLog.objects.filter(pk=log.pk).exists())
        self.assertFalse(Follow.objects.filter(follower=self.user).exists())
        self.assertFalse(Follow.objects.filter(following=self.user).exists())
        self.assertFalse(SocialAccount.objects.filter(user=self.user).exists())
        # 같은 카카오 계정으로 다시 연결할 수 있어야 한다 (조건부 유니크)
        SocialAccount.objects.create(
            user=self.other, provider="kakao", provider_uid="k-1"
        )

    def test_withdraw_leaves_crews(self):
        crew = create_crew(self.other, name="남는크루")
        add_member(crew, self.user)
        pending_crew = create_crew(self.other, name="대기크루", join_type="approval")
        add_member(pending_crew, self.user, status="pending")

        self.assertEqual(self._withdraw().status_code, 204)

        self.assertFalse(CrewMember.objects.filter(user=self.user).exists())
        self.assertFalse(
            ChatRoomMember.objects.filter(room=crew.chat_room, user=self.user).exists()
        )
        self.assertTrue(
            Message.objects.filter(
                room=crew.chat_room, content__contains="나갔습니다"
            ).exists()
        )

    def test_crew_owner_cannot_withdraw(self):
        crew = create_crew(self.user, name="내크루")
        response = self._withdraw()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "crew_owner")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(CrewMember.objects.filter(crew=crew, user=self.user).exists())

    def test_refresh_tokens_blacklisted_after_withdraw(self):
        refresh = str(RefreshToken.for_user(self.user))
        self.assertEqual(self._withdraw().status_code, 204)
        self.client.force_authenticate(None)
        response = self.client.post(self.refresh_url, {"refresh": refresh})
        self.assertEqual(response.status_code, 401)

    def test_same_email_and_nickname_can_register_again(self):
        self.assertEqual(self._withdraw().status_code, 204)
        self.client.force_authenticate(None)
        response = self.client.post(
            self.register_url,
            {"email": "bye@example.com", "nickname": "bye", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 201)

    def test_public_profile_404_after_withdraw(self):
        self.assertEqual(self._withdraw().status_code, 204)
        self.client.force_authenticate(self.other)
        response = self.client.get(reverse("v1:accounts:detail", args=[self.user.id]))
        self.assertEqual(response.status_code, 404)

    def test_social_only_account_withdraws_without_password(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        response = self.client.delete(self.url, {})
        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
