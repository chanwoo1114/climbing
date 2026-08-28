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
    _blacklist_all_refresh_tokens(user)
    return user


def _blacklist_all_refresh_tokens(user: User) -> None:
    """다른 기기 세션 종료 — 발급된 refresh 토큰을 전부 블랙리스트에 올린다."""
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


@transaction.atomic
def change_password(*, user: User, current_password: str, new_password: str) -> dict:
    """로그인 상태에서 비밀번호 변경.

    - 소셜 로그인만 연결된 계정(비밀번호 없음)은 400 no_password
      → auth/password-reset/ 로 먼저 만들어야 한다
    - 현재 비밀번호가 틀리면 필드 오류 (current_password)
    - 새 비밀번호 규칙은 가입과 동일 (validate_password + 유사도 검사에 user 전달)
    - 기존 refresh 토큰은 전부 블랙리스트 → 다른 기기 세션 종료. 이 기기는 계속 쓰도록
      새 토큰 쌍을 돌려준다
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    from accounts.exceptions import NoPassword

    if not user.has_usable_password():
        raise NoPassword()
    if not user.check_password(current_password):
        raise serializers.ValidationError(
            {"current_password": ["현재 비밀번호가 올바르지 않습니다."]}
        )
    if current_password == new_password:
        raise serializers.ValidationError(
            {"new_password": ["현재 비밀번호와 다른 비밀번호를 입력해 주세요."]}
        )
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"new_password": list(exc.messages)})

    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    _blacklist_all_refresh_tokens(user)

    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def withdrawn_email(user_id: int) -> str:
    return f"withdrawn-{user_id}@withdrawn.invalid"


def withdrawn_nickname(user_id: int) -> str:
    return f"탈퇴회원_{user_id}"


@transaction.atomic
def withdraw_user(*, user: User, password: str = "") -> User:
    """회원 탈퇴 (soft delete).

    - 비밀번호가 있는 계정은 비밀번호 재확인, 소셜 전용 계정은 그대로 진행
    - 크루장인 크루가 남아 있으면 409 crew_owner (크루를 먼저 삭제해야 한다 —
      Crew.owner 가 CASCADE 라 그냥 지우면 크루원 전원이 크루를 잃는다)
    - 활동 중/대기 중인 크루는 탈퇴 처리 (단톡방 퇴장 + 시스템 메시지)
    - 이메일·닉네임은 자리표시자로 바꿔 같은 이메일로 재가입할 수 있게 한다
      (Lower(email)/Lower(nickname) 유니크 제약은 soft delete 행도 포함하므로)
    - 비밀번호는 사용 불가로, is_active=False, refresh 토큰 전부 블랙리스트
    - User.delete() 가 CASCADE 자식(프로필·기록·댓글·좋아요·팔로우·소셜 연결·알림·
      채팅방 참여)을 함께 soft delete 한다. 채팅 메시지는 SET_NULL 이라 남는다
    """
    from accounts.exceptions import CrewOwnerCannotWithdraw
    from crews.models import Crew, CrewMember
    from crews.services import leave_crew

    if user.has_usable_password():
        if not password:
            raise serializers.ValidationError(
                {"password": ["비밀번호를 입력해 주세요."]}
            )
        if not user.check_password(password):
            raise serializers.ValidationError(
                {"password": ["비밀번호가 올바르지 않습니다."]}
            )
    if Crew.objects.filter(owner=user).exists():
        raise CrewOwnerCannotWithdraw()

    memberships = CrewMember.objects.filter(user=user).select_related("crew__chat_room")
    for membership in memberships:
        leave_crew(membership.crew, user)

    _blacklist_all_refresh_tokens(user)

    user.email = withdrawn_email(user.pk)
    user.nickname = withdrawn_nickname(user.pk)
    user.is_active = False
    user.set_unusable_password()
    user.save(
        update_fields=["email", "nickname", "is_active", "password", "updated_at"]
    )
    user.delete()
    return user
