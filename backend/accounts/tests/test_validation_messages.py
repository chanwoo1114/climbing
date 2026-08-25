"""회원가입/로그인 검증 메시지 — 프론트가 필드별로 빨간 메시지를 띄우는 근거."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.services import register_user


class RegisterValidationTests(APITestCase):
    url = reverse("v1:auth:register")

    @classmethod
    def setUpTestData(cls):
        register_user(
            email="taken@example.com", nickname="이미쓰는닉", password="s3cure-pass!"
        )

    def _post(self, **overrides):
        payload = {
            "email": "new@example.com",
            "nickname": "새닉네임",
            "password": "s3cure-pass!",
        }
        payload.update(overrides)
        return self.client.post(self.url, payload)

    def test_duplicate_email_returns_field_error(self):
        response = self._post(email="taken@example.com")
        self.assertEqual(response.status_code, 400)
        error = response.json()["error"]
        self.assertEqual(error["fields"]["email"], ["이미 가입된 이메일입니다."])

    def test_duplicate_nickname_returns_field_error(self):
        response = self._post(nickname="이미쓰는닉")
        self.assertEqual(response.status_code, 400)
        error = response.json()["error"]
        self.assertEqual(error["fields"]["nickname"], ["이미 사용 중인 닉네임입니다."])

    def test_invalid_email_format(self):
        response = self._post(email="not-an-email")
        self.assertEqual(response.status_code, 400)
        self.assertIn("이메일 형식", response.json()["error"]["fields"]["email"][0])

    def test_short_password_returns_field_error(self):
        response = self._post(password="short1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])

    def test_numeric_only_password_rejected(self):
        response = self._post(password="12345678901")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])

    def test_valid_payload_succeeds(self):
        self.assertEqual(self._post().status_code, 201)


class LoginMessageTests(APITestCase):
    url = reverse("v1:auth:login")

    @classmethod
    def setUpTestData(cls):
        register_user(
            email="login@example.com", nickname="로그인", password="s3cure-pass!"
        )

    def test_wrong_password_message_is_generic(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": "wrong-pass!"}
        )
        self.assertEqual(response.status_code, 401)
        message = response.json()["error"]["message"]
        self.assertEqual(message, "이메일 또는 비밀번호가 올바르지 않습니다.")

    def test_unknown_email_gives_same_message(self):
        # 계정 존재 여부가 메시지로 새어나가면 안 된다.
        response = self.client.post(
            self.url, {"email": "nobody@example.com", "password": "s3cure-pass!"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["error"]["message"],
            "이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    def test_login_succeeds(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": "s3cure-pass!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json()["data"])


class NicknameRuleTests(APITestCase):
    """닉네임 규칙은 프론트가 아니라 서버가 최종 판정한다.

    API를 직접 호출하는 경우에도 동일하게 막혀야 한다.
    """

    url = reverse("v1:auth:register")

    def _register(self, nickname):
        return self.client.post(
            self.url,
            {
                "email": f"n{abs(hash(nickname)) % 10000}@example.com",
                "nickname": nickname,
                "password": "s3cure-pass!",
            },
        )

    def test_too_short_nickname_rejected(self):
        response = self._register("x")
        self.assertEqual(response.status_code, 400)
        self.assertIn("2자 이상", response.json()["error"]["fields"]["nickname"][0])

    def test_special_characters_rejected(self):
        response = self._register("해커!!@#")
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "한글, 영문, 숫자", response.json()["error"]["fields"]["nickname"][0]
        )

    def test_too_long_nickname_rejected(self):
        response = self._register("가" * 31)
        self.assertEqual(response.status_code, 400)
        self.assertIn("30자 이하", response.json()["error"]["fields"]["nickname"][0])

    def test_whitespace_only_nickname_rejected(self):
        response = self._register("   ")
        self.assertEqual(response.status_code, 400)

    def test_valid_nicknames_accepted(self):
        for nickname in ("볼더왕", "climber_01", "초크"):
            with self.subTest(nickname=nickname):
                self.assertEqual(self._register(nickname).status_code, 201)


class MeNicknameRuleTests(APITestCase):
    """프로필 수정에도 같은 규칙이 걸린다."""

    url = reverse("v1:accounts:me")

    def setUp(self):
        self.user = register_user(
            email="me@example.com", nickname="원래닉", password="s3cure-pass!"
        )
        self.client.force_authenticate(self.user)

    def test_invalid_nickname_rejected_on_update(self):
        response = self.client.patch(self.url, {"nickname": "?!"})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "원래닉")

    def test_duplicate_nickname_rejected_on_update(self):
        register_user(
            email="other@example.com", nickname="남의닉", password="s3cure-pass!"
        )
        response = self.client.patch(self.url, {"nickname": "남의닉"})
        self.assertEqual(response.status_code, 400)

    def test_keeping_own_nickname_is_allowed(self):
        # 자기 닉네임 그대로 보내는 건 중복이 아니다.
        response = self.client.patch(self.url, {"nickname": "원래닉", "bio": "안녕"})
        self.assertEqual(response.status_code, 200)

    def test_valid_nickname_updated(self):
        response = self.client.patch(self.url, {"nickname": "새로운닉"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "새로운닉")


class LengthLimitTests(APITestCase):
    """길이 상한이 시리얼라이저에서 걸려야 한다.

    막지 않으면 DB 컬럼(varchar 254)까지 내려가 DataError(500)가 난다.
    검증 실패는 500이 아니라 400으로 돌려주는 게 맞다.
    """

    register_url = reverse("v1:auth:register")
    login_url = reverse("v1:auth:login")

    def test_too_long_email_returns_400_not_500(self):
        long_email = "a" * 250 + "@example.com"  # 262자
        response = self.client.post(
            self.register_url,
            {"email": long_email, "nickname": "긴메일", "password": "s3cure-pass!"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("254자", response.json()["error"]["fields"]["email"][0])

    def test_email_at_limit_is_accepted(self):
        # 로컬파트 242 + "@example.com"(12) = 254자
        email = "a" * 242 + "@example.com"
        self.assertEqual(len(email), 254)
        response = self.client.post(
            self.register_url,
            {"email": email, "nickname": "경계값", "password": "s3cure-pass!"},
        )
        self.assertEqual(response.status_code, 201)

    def test_too_long_password_returns_400(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "longpw@example.com",
                "nickname": "긴비번",
                "password": "x7q!w9e$r2t" * 2,  # 22자 — 상한 16자 초과
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("16자", response.json()["error"]["fields"]["password"][0])

    def test_login_rejects_oversized_input(self):
        # 해시 연산까지 내려가지 않고 검증 단계에서 끊긴다.
        response = self.client.post(
            self.login_url,
            {"email": "a" * 300 + "@example.com", "password": "b" * 500},
        )
        self.assertEqual(response.status_code, 400)


class PasswordSimilarityTests(APITestCase):
    """비밀번호-사용자정보 유사도 검사.

    validate_password 를 user 없이 부르면 이 검사가 통째로 건너뛰어진다.
    회귀하면 이메일과 같은 비밀번호가 통과한다.
    """

    url = reverse("v1:auth:register")

    def _register(self, email, nickname, password):
        return self.client.post(
            self.url, {"email": email, "nickname": nickname, "password": password}
        )

    def test_password_same_as_email_rejected(self):
        # 16자 상한 안에서 이메일과 유사한 값 (climber@example = 15자)
        response = self._register(
            "climber@example.com", "유사검사", "climber@example"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("유사", response.json()["error"]["fields"]["password"][0])

    def test_password_containing_email_local_part_rejected(self):
        response = self._register("mountain@example.com", "유사검사2", "mountain99")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])

    def test_password_similar_to_nickname_rejected(self):
        response = self._register("ok@example.com", "climbmaster", "climbmaster1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])

    def test_unrelated_password_accepted(self):
        response = self._register("fine@example.com", "정상닉", "tr4verse-wall!")
        self.assertEqual(response.status_code, 201)
