"""카카오 소셜 로그인 (accounts/social).

카카오 HTTP 호출(exchange_code / fetch_profile)은 mock 한다. state 는 서명 검증만
본다. 카카오 토큰은 어디에도 저장되지 않아야 한다 (docs/개발정의.md 5장 5번).
"""

import unicodedata
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import SocialAccount, User, UserProfile
from accounts.social.kakao import KakaoProfile, make_state
from accounts.social.services import sanitize_nickname
from accounts.tests.helpers import create_verified_user
from accounts.throttles import SocialLoginRateThrottle
from accounts.views import KakaoCallbackView

KAKAO_SETTINGS = {
    "KAKAO_CLIENT_ID": "test-rest-api-key",
    "KAKAO_CLIENT_SECRET": "",
    "KAKAO_REDIRECT_URI": "http://localhost:5180/auth/kakao/callback",
    "KAKAO_STATE_TIMEOUT": 600,
}


def profile(**overrides) -> KakaoProfile:
    base = {
        "uid": "123456789",
        "email": "kakao@example.com",
        "email_verified": True,
        "nickname": "카카오유저",
        "image_url": "http://k.kakaocdn.net/dn/abc/img_640x640.jpg",
    }
    base.update(overrides)
    return KakaoProfile(**base)


@override_settings(**KAKAO_SETTINGS)
class KakaoAuthorizeTests(APITestCase):
    url = reverse("v1:auth:kakao-authorize")

    def test_returns_authorize_url_with_signed_state(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(
            data["authorize_url"].startswith("https://kauth.kakao.com/oauth/authorize?")
        )
        self.assertIn("client_id=test-rest-api-key", data["authorize_url"])
        self.assertIn("response_type=code", data["authorize_url"])
        self.assertIn(
            "redirect_uri=http%3A%2F%2Flocalhost%3A5180%2Fauth%2Fkakao%2Fcallback",
            data["authorize_url"],
        )
        # state 는 URL 과 응답 본문에 같은 값으로 들어 있다 (프론트가 비교용으로 보관).
        query = parse_qs(urlsplit(data["authorize_url"]).query)
        self.assertEqual(query["state"], [data["state"]])
        self.assertIn(":", data["state"])  # TimestampSigner 서명 형식

    @override_settings(KAKAO_CLIENT_ID="")
    def test_not_configured_returns_503(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "kakao_not_configured")


@override_settings(**KAKAO_SETTINGS)
class KakaoCallbackTests(APITestCase):
    url = reverse("v1:auth:kakao-callback")

    def _callback(self, kakao_profile=None, state=None, code="auth-code"):
        """카카오 HTTP 를 mock 하고 콜백을 호출한다."""
        kakao_profile = kakao_profile or profile()
        state = state if state is not None else make_state()
        with (
            patch(
                "accounts.social.kakao.exchange_code", return_value="kakao-access"
            ) as exchange,
            patch(
                "accounts.social.kakao.fetch_profile", return_value=kakao_profile
            ) as fetch,
        ):
            response = self.client.post(
                self.url, {"code": code, "state": state}, format="json"
            )
        self.exchange_mock, self.fetch_mock = exchange, fetch
        return response

    # ---- state ----------------------------------------------------------------

    def test_forged_state_is_rejected_before_calling_kakao(self):
        response = self._callback(state="garbage:state")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_state")
        self.exchange_mock.assert_not_called()

    def test_expired_state_is_rejected(self):
        state = make_state()
        with override_settings(KAKAO_STATE_TIMEOUT=-1):
            response = self._callback(state=state)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_state")

    def test_missing_fields_returns_400(self):
        response = self.client.post(self.url, {"code": "x"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("state", response.json()["error"]["fields"])

    # ---- 신규 가입 -------------------------------------------------------------

    def test_new_user_is_created_with_tokens(self):
        response = self._callback()
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertTrue(data["is_new"])
        self.exchange_mock.assert_called_once_with("auth-code")
        self.fetch_mock.assert_called_once_with("kakao-access")

        user = User.objects.get(email="kakao@example.com")
        self.assertEqual(user.nickname, "카카오유저")
        self.assertIsNotNone(user.email_verified_at)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(
            user.profile.image, "http://k.kakaocdn.net/dn/abc/img_640x640.jpg"
        )
        account = SocialAccount.objects.get(user=user)
        self.assertEqual(account.provider, "kakao")
        self.assertEqual(account.provider_uid, "123456789")
        self.assertEqual(account.email_at_provider, "kakao@example.com")
        self.assertEqual(account.nickname_at_provider, "카카오유저")
        # 토큰은 어디에도 남지 않는다.
        self.assertFalse(
            any("token" in f.name for f in SocialAccount._meta.get_fields())
        )

    def test_access_token_works_for_me(self):
        access = self._callback().json()["data"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get(reverse("v1:accounts:me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["email"], "kakao@example.com")

    def test_new_user_without_email_gets_placeholder(self):
        response = self._callback(profile(email=None, email_verified=False))
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(social_accounts__provider_uid="123456789")
        self.assertEqual(user.email, "kakao_123456789@kakao.local")
        self.assertIsNotNone(user.email_verified_at)

    def test_unverified_kakao_email_is_not_trusted_for_new_user(self):
        # 남의 이메일을 카카오에 미인증으로 넣어 두고 가입해도 그 주소를 못 가져간다.
        self._callback(profile(email="victim@example.com", email_verified=False))
        user = User.objects.get(social_accounts__provider_uid="123456789")
        self.assertEqual(user.email, "kakao_123456789@kakao.local")

    def test_nickname_is_sanitized_and_deduplicated(self):
        create_verified_user(email="a@example.com", nickname="Chalk")
        response = self._callback(profile(nickname="  chalk ★!! "))
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="kakao@example.com")
        self.assertEqual(user.nickname, "chalk2")  # 대소문자 무시 중복 → 접미사

    def test_too_short_nickname_falls_back(self):
        self._callback(profile(nickname="★"))
        user = User.objects.get(email="kakao@example.com")
        self.assertEqual(user.nickname, "클라이머")

    def test_long_nickname_is_truncated_to_30(self):
        self._callback(profile(nickname="a" * 40))
        user = User.objects.get(email="kakao@example.com")
        self.assertEqual(len(user.nickname), 30)

    # ---- 기존 연결 / 이메일 연결 ---------------------------------------------

    def test_existing_social_account_logs_in_same_user(self):
        first = self._callback()
        user = User.objects.get(email="kakao@example.com")
        # 닉네임·이메일이 바뀌어도 uid 로 같은 회원을 찾는다.
        second = self._callback(profile(nickname="바뀐닉", email="new@example.com"))
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["data"]["is_new"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.filter(user=user).count(), 1)
        user.refresh_from_db()
        self.assertEqual(user.nickname, "카카오유저")
        self.assertIsNotNone(user.last_login)  # UPDATE_LAST_LOGIN

    def test_existing_email_user_is_linked_when_kakao_email_verified(self):
        existing = create_verified_user(email="kakao@example.com", nickname="기존")
        response = self._callback(profile(nickname="다른닉"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["is_new"])
        self.assertEqual(User.objects.count(), 1)
        account = SocialAccount.objects.get(provider_uid="123456789")
        self.assertEqual(account.user, existing)
        existing.refresh_from_db()
        self.assertEqual(existing.nickname, "기존")
        self.assertTrue(existing.has_usable_password())

    def test_email_match_is_case_insensitive(self):
        create_verified_user(email="Mixed.Case@example.com", nickname="기존")
        response = self._callback(profile(email="mixed.case@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_linking_marks_unverified_local_account_as_verified(self):
        from accounts.services import register_user

        user = register_user(
            email="kakao@example.com", nickname="미인증", password="s3cure-pass!"
        )
        self.assertIsNone(user.email_verified_at)
        self.assertEqual(self._callback().status_code, 200)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)

    def test_unverified_kakao_email_conflict_returns_409(self):
        create_verified_user(email="kakao@example.com", nickname="기존")
        response = self._callback(profile(email_verified=False))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "email_conflict")
        self.assertFalse(SocialAccount.objects.exists())
        self.assertEqual(User.objects.count(), 1)

    # ---- 계정 상태 / 카카오 장애 -----------------------------------------------

    def test_soft_deleted_user_returns_401(self):
        self._callback()
        User.objects.get(email="kakao@example.com").delete()  # soft delete
        response = self._callback()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "user_inactive")
        self.assertEqual(User.objects.count(), 0)  # 새로 만들지도 않는다

    def test_inactive_user_returns_401(self):
        self._callback()
        User.objects.filter(email="kakao@example.com").update(is_active=False)
        response = self._callback()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "user_inactive")

    def test_kakao_http_failure_returns_502(self):
        from accounts.social.exceptions import KakaoError

        with patch("accounts.social.kakao.exchange_code", side_effect=KakaoError()):
            response = self.client.post(
                self.url, {"code": "bad", "state": make_state()}, format="json"
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "kakao_error")
        self.assertEqual(User.objects.count(), 0)

    def test_kakao_http_error_is_mapped_at_transport_level(self):
        """urlopen 이 HTTPError 를 내면 kakao.exchange_code 가 KakaoError 로 바꾼다."""
        from urllib.error import HTTPError

        from accounts.social import kakao

        with patch(
            "accounts.social.kakao.urlopen",
            side_effect=HTTPError("u", 400, "Bad Request", {}, None),
        ):
            with self.assertRaises(kakao.KakaoError):
                kakao.exchange_code("bad")

    def test_callback_has_login_style_throttle(self):
        self.assertIn(SocialLoginRateThrottle, KakaoCallbackView.throttle_classes)


class SanitizeNicknameTests(APITestCase):
    def test_keeps_allowed_characters_only(self):
        self.assertEqual(sanitize_nickname("홍길동 (Kakao) #1"), "홍길동Kakao1")

    def test_normalizes_decomposed_hangul(self):
        # macOS 등에서 오는 NFD 자모도 완성형으로 합친다.
        decomposed = unicodedata.normalize("NFD", "홍길동")
        self.assertNotEqual(decomposed, "홍길동")
        self.assertEqual(sanitize_nickname(decomposed), "홍길동")

    def test_suffix_skips_taken_numbers(self):
        create_verified_user(email="a@example.com", nickname="chalk")
        create_verified_user(email="b@example.com", nickname="chalk2")
        self.assertEqual(sanitize_nickname("chalk"), "chalk3")

    def test_suffix_respects_max_length(self):
        create_verified_user(email="a@example.com", nickname="x" * 30)
        result = sanitize_nickname("x" * 30)
        self.assertEqual(len(result), 30)
        self.assertTrue(result.endswith("2"))


@override_settings(**KAKAO_SETTINGS)
class SocialAccountManageTests(APITestCase):
    list_url = reverse("v1:auth:social-list")
    unlink_url = reverse("v1:auth:social-unlink", kwargs={"provider": "kakao"})

    def _kakao_login(self, kakao_profile=None):
        with (
            patch("accounts.social.kakao.exchange_code", return_value="t"),
            patch(
                "accounts.social.kakao.fetch_profile",
                return_value=kakao_profile or profile(),
            ),
        ):
            response = self.client.post(
                reverse("v1:auth:kakao-callback"),
                {"code": "c", "state": make_state()},
                format="json",
            )
        return response.json()["data"]

    def _auth(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_list_requires_auth(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 401)
        self.assertEqual(self.client.delete(self.unlink_url).status_code, 401)

    def test_list_shows_linked_providers_without_uid(self):
        self._auth(self._kakao_login()["access"])
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["provider"], "kakao")
        self.assertEqual(data[0]["email_at_provider"], "kakao@example.com")
        self.assertIn("connected_at", data[0])
        self.assertNotIn("provider_uid", data[0])

    def test_list_is_empty_for_password_user(self):
        user = create_verified_user()
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.list_url).json()["data"], [])

    def test_unlink_blocked_when_it_is_the_only_login_method(self):
        self._auth(self._kakao_login()["access"])
        response = self.client.delete(self.unlink_url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "last_login_method")
        self.assertTrue(SocialAccount.objects.exists())

    def test_unlink_allowed_when_password_exists(self):
        existing = create_verified_user(email="kakao@example.com", nickname="기존")
        self._auth(self._kakao_login()["access"])  # 이메일로 연결됨
        response = self.client.delete(self.unlink_url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SocialAccount.objects.filter(user=existing).exists())
        # soft delete — 행은 남는다
        self.assertTrue(SocialAccount.all_objects.filter(user=existing).exists())
        self.assertEqual(self.client.get(self.list_url).json()["data"], [])

    def test_relink_after_unlink_creates_new_row(self):
        create_verified_user(email="kakao@example.com", nickname="기존")
        self._auth(self._kakao_login()["access"])
        self.client.delete(self.unlink_url)
        self.client.credentials()
        data = self._kakao_login()
        self.assertFalse(data["is_new"])
        self.assertEqual(SocialAccount.objects.count(), 1)
        self.assertEqual(SocialAccount.all_objects.count(), 2)
        self.assertEqual(User.objects.count(), 1)

    def test_unlink_unknown_or_missing_provider_returns_404(self):
        self.client.force_authenticate(create_verified_user())
        self.assertEqual(self.client.delete(self.unlink_url).status_code, 404)
        response = self.client.delete(
            reverse("v1:auth:social-unlink", kwargs={"provider": "naver"})
        )
        self.assertEqual(response.status_code, 404)

    def test_soft_deleting_user_cascades_to_social_account(self):
        self._kakao_login()
        user = User.objects.get(email="kakao@example.com")
        user.delete()
        self.assertFalse(SocialAccount.objects.exists())
        self.assertTrue(SocialAccount.all_objects.filter(user=user).exists())
        self.assertFalse(UserProfile.objects.filter(user=user).exists())
