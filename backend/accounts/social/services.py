"""카카오 로그인 비즈니스 로직. HTTP 는 accounts.social.kakao, 뷰는 얇게."""

import re
import unicodedata

from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.exceptions import UserInactive
from accounts.models import SocialAccount, User, UserProfile
from accounts.serializers import NICKNAME_MAX_LENGTH, NICKNAME_MIN_LENGTH
from accounts.social import kakao
from accounts.social.exceptions import EmailConflict, LastLoginMethod
from accounts.social.kakao import KakaoProfile

KAKAO = SocialAccount.Provider.KAKAO
FALLBACK_NICKNAME = "클라이머"
# NICKNAME_FORMAT_VALIDATOR(serializers.py) 허용 문자의 여집합 — 제거 대상
_NICKNAME_DISALLOWED = re.compile(r"[^가-힣a-zA-Z0-9_-]")
_PROFILE_IMAGE_MAX_LENGTH = UserProfile._meta.get_field("image").max_length


def issue_tokens(user: User) -> dict:
    """LoginView 와 같은 JWT 쌍 발급 (+ UPDATE_LAST_LOGIN)."""
    refresh = RefreshToken.for_user(user)
    if jwt_settings.UPDATE_LAST_LOGIN:
        update_last_login(None, user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def sanitize_nickname(raw: str) -> str:
    """카카오 닉네임을 우리 닉네임 규칙(한글/영문/숫자/_-, 2~30자)에 맞추고 중복이면
    숫자 접미사를 붙인다 (대소문자 무시, 탈퇴 계정 포함 — DB UNIQUE 와 동일 기준)."""
    base = _NICKNAME_DISALLOWED.sub("", unicodedata.normalize("NFC", raw or ""))
    if len(base) < NICKNAME_MIN_LENGTH:
        base = FALLBACK_NICKNAME
    base = base[:NICKNAME_MAX_LENGTH]

    def taken(candidate: str) -> bool:
        return User.all_objects.filter(nickname__iexact=candidate).exists()

    if not taken(base):
        return base
    suffix = 2
    while True:
        tail = str(suffix)
        candidate = f"{base[: NICKNAME_MAX_LENGTH - len(tail)]}{tail}"
        if not taken(candidate):
            return candidate
        suffix += 1


def _placeholder_email(uid: str) -> str:
    # 이메일 동의를 안 했거나 미인증인 경우. 카카오 회원번호 자체가 신원이므로
    # 계정은 만들되, 메일을 받을 수 없는 주소라는 걸 도메인으로 드러낸다.
    return f"kakao_{uid}@kakao.local"


def _link(user: User, profile: KakaoProfile) -> SocialAccount:
    return SocialAccount.objects.create(
        user=user,
        provider=KAKAO,
        provider_uid=profile.uid,
        email_at_provider=profile.email or "",
        nickname_at_provider=profile.nickname[:100],
    )


def _register(profile: KakaoProfile) -> User:
    email = profile.email if profile.email_verified else None
    # 탈퇴 계정이 그 이메일을 쥐고 있으면 UNIQUE 충돌 → 자리표시자로 만든다.
    if email and User.all_objects.filter(email__iexact=email).exists():
        email = None
    user = User(
        email=User.objects.normalize_email(email or _placeholder_email(profile.uid)),
        nickname=sanitize_nickname(profile.nickname),
        # 카카오가 신원을 보증하므로 별도 인증 메일 없이 바로 로그인 가능 상태.
        email_verified_at=timezone.now(),
    )
    user.set_unusable_password()  # 비밀번호는 재설정 메일로 나중에 만들 수 있다
    user.save()
    image = profile.image_url
    if len(image) > _PROFILE_IMAGE_MAX_LENGTH:
        image = ""
    UserProfile.objects.create(user=user, image=image)
    return user


@transaction.atomic
def login_or_register_kakao(profile: KakaoProfile) -> tuple[User, bool]:
    """(user, is_new).

    1. 이미 연결된 카카오 계정 → 그 회원 (탈퇴·비활성이면 401 user_inactive)
    2. 같은 이메일의 회원이 있으면 연결 — 단 카카오 쪽 이메일이 인증된 경우만
       (미인증이면 409 email_conflict: 남의 이메일로 계정 탈취 방지)
    3. 없으면 새 회원 생성 (비밀번호 없음, 이메일 인증 완료 상태)
    """
    account = (
        SocialAccount.all_objects.filter(provider=KAKAO, provider_uid=profile.uid)
        .select_related("user")
        .order_by("-id")
        .first()
    )
    if account is not None:
        user = account.user
        if user.is_deleted or not user.is_active:
            raise UserInactive()
        if not account.is_deleted:
            return user, False
        # 연결 해제(soft delete)된 상태 → 아래에서 이메일 기준으로 다시 연결/가입

    if profile.email:
        existing = User.objects.filter(email__iexact=profile.email).first()
        if existing is not None:
            if not profile.email_verified:
                raise EmailConflict()
            if not existing.is_active:
                raise UserInactive()
            _link(existing, profile)
            if existing.email_verified_at is None:
                # 카카오가 같은 주소의 소유를 확인해 줬으므로 인증된 것으로 본다.
                existing.email_verified_at = timezone.now()
                existing.save(update_fields=["email_verified_at", "updated_at"])
            return existing, False

    user = _register(profile)
    _link(user, profile)
    return user, True


def login_with_kakao_code(code: str) -> tuple[User, bool]:
    """인가 코드 → 카카오 프로필 → 회원. 카카오 토큰은 이 함수 안에서만 살고 버려진다."""
    access_token = kakao.exchange_code(code)
    profile = kakao.fetch_profile(access_token)
    return login_or_register_kakao(profile)


def linked_accounts(user: User):
    return user.social_accounts.order_by("connected_at")


@transaction.atomic
def unlink(user: User, provider: str) -> SocialAccount | None:
    """연결 해제 (soft delete). 없으면 None. 비밀번호가 없는 계정의 마지막 연결이면 400."""
    accounts = list(
        SocialAccount.objects.select_for_update().filter(user=user).order_by("id")
    )
    target = next((a for a in accounts if a.provider == provider), None)
    if target is None:
        return None
    if not user.has_usable_password() and len(accounts) == 1:
        raise LastLoginMethod()
    target.delete()
    return target
