"""이메일 인증 / 비밀번호 재설정 토큰.

둘 다 DB 테이블 없이 서명으로 검증한다.
- 이메일 인증: TimestampSigner. 만료(EMAIL_VERIFICATION_TIMEOUT)만 본다.
  이미 인증된 계정이 다시 눌러도 해가 없으므로 1회성 강제는 하지 않는다.
- 비밀번호 재설정: Django 내장 PasswordResetTokenGenerator. 토큰에 현재 비밀번호
  해시가 섞여 있어 비밀번호가 바뀌는 순간 자동으로 무효화된다 (1회성).
  만료는 settings.PASSWORD_RESET_TIMEOUT.
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from accounts.models import User

_VERIFY_SALT = "accounts.email-verification"


def make_email_verification_token(user) -> str:
    return signing.TimestampSigner(salt=_VERIFY_SALT).sign_object(
        {"uid": user.pk, "email": user.email}
    )


def read_email_verification_token(token: str):
    """토큰이 가리키는 사용자. 위조·만료·이메일 불일치·탈퇴면 None."""
    try:
        payload = signing.TimestampSigner(salt=_VERIFY_SALT).unsign_object(
            token, max_age=settings.EMAIL_VERIFICATION_TIMEOUT
        )
    except signing.BadSignature:
        return None
    user = User.objects.filter(pk=payload.get("uid")).first()
    if user is None or user.email != payload.get("email"):
        return None
    return user


def make_password_reset_credentials(user) -> tuple[str, str]:
    """(uid, token) — 프론트 링크 쿼리스트링에 실어 보낸다."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return uid, default_token_generator.make_token(user)


def read_password_reset_credentials(uid: str, token: str):
    """(uid, token) 이 가리키는 사용자. 위조·만료·사용됨·탈퇴면 None."""
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=pk)
    except (ValueError, TypeError, OverflowError, User.DoesNotExist):
        return None
    if not default_token_generator.check_token(user, token):
        return None
    return user
