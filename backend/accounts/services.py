from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from accounts.emails import send_password_reset_email, send_verification_email
from accounts.exceptions import InvalidToken
from accounts.models import User, UserProfile
from accounts.tokens import (
    read_email_verification_token,
    read_password_reset_credentials,
)


@transaction.atomic
def register_user(*, email: str, nickname: str, password: str) -> User:
    """유저 + 빈 프로필을 한 트랜잭션으로 생성하고, 커밋 후 인증 메일을 보낸다."""
    user = User.objects.create_user(email=email, nickname=nickname, password=password)
    UserProfile.objects.create(user=user)
    # 커밋 전에 큐에 넣으면 워커가 아직 없는 유저를 조회할 수 있다.
    transaction.on_commit(lambda: send_verification_email(user))
    return user


def ensure_profile(user: User) -> UserProfile:
    """프로필이 없는 계정(createsuperuser·admin 생성)에 빈 프로필을 붙인다."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def verify_email(*, token: str) -> User:
    """인증 링크의 토큰을 확인하고 email_verified_at 을 찍는다. 재클릭은 no-op."""
    user = read_email_verification_token(token)
    if user is None:
        raise InvalidToken()
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
    return user


def resend_verification_email(*, email: str) -> None:
    """계정 존재 여부·인증 여부와 무관하게 조용히 처리한다 (계정 열거 방지)."""
    user = User.objects.filter(email__iexact=email).first()
    if user is not None and user.email_verified_at is None:
        send_verification_email(user)


def request_password_reset(*, email: str) -> None:
    """존재하는 계정에만 메일을 보내되, 응답은 항상 동일하다 (계정 열거 방지)."""
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        send_password_reset_email(user)


@transaction.atomic
def confirm_password_reset(*, uid: str, token: str, password: str) -> User:
    """재설정 링크로 새 비밀번호를 설정한다.

    - 비밀번호 규칙은 가입과 동일 (validate_password + 유사도 검사에 user 전달)
    - 기존 refresh 토큰을 전부 블랙리스트 → 다른 기기 세션 종료
    - 메일 링크를 열었다는 건 메일 소유 증명이므로 미인증 계정은 인증 처리
    """
    user = read_password_reset_credentials(uid, token)
    if user is None:
        raise InvalidToken()
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)})

    user.set_password(password)
    update_fields = ["password", "updated_at"]
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        update_fields.append("email_verified_at")
    user.save(update_fields=update_fields)

    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)
    return user
