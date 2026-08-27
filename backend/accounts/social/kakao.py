"""카카오 OAuth 클라이언트 — HTTP 는 전부 여기서만 한다 (테스트는 이 함수들을 mock).

state 는 세션 없이 서명으로 검증한다 (TimestampSigner, KAKAO_STATE_TIMEOUT 초).
프론트는 authorize 응답의 state 를 sessionStorage 에 두었다가 콜백 쿼리의 state 와
같은지 한 번 더 비교하면 브라우저 단에서도 CSRF 를 막을 수 있다.
"""

import json
import secrets
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core import signing

from accounts.social.exceptions import InvalidState, KakaoError, KakaoNotConfigured

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
PROFILE_URL = "https://kapi.kakao.com/v2/user/me"
TIMEOUT_SECONDS = 10

_STATE_SALT = "accounts.kakao-oauth-state"


@dataclass(frozen=True)
class KakaoProfile:
    """카카오 /v2/user/me 에서 우리가 쓰는 값만 추린 것. 토큰은 담지 않는다."""

    uid: str
    email: str | None
    email_verified: bool
    nickname: str
    image_url: str


def _client_id() -> str:
    client_id = settings.KAKAO_CLIENT_ID
    if not client_id:
        raise KakaoNotConfigured()
    return client_id


# ---- state ------------------------------------------------------------------


def make_state() -> str:
    return signing.TimestampSigner(salt=_STATE_SALT).sign(secrets.token_urlsafe(16))


def check_state(state: str) -> None:
    try:
        signing.TimestampSigner(salt=_STATE_SALT).unsign(
            state, max_age=settings.KAKAO_STATE_TIMEOUT
        )
    except signing.BadSignature:
        raise InvalidState()


def build_authorize_url() -> tuple[str, str]:
    """(authorize_url, state)."""
    state = make_state()
    query = urlencode(
        {
            "client_id": _client_id(),
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
            "response_type": "code",
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}", state


# ---- HTTP -------------------------------------------------------------------


def _request_json(request: Request) -> dict:
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise KakaoError(f"카카오 응답 오류 ({exc.code})") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise KakaoError() from exc
    if not isinstance(payload, dict) or "error" in payload:
        raise KakaoError()
    return payload


def exchange_code(code: str) -> str:
    """인가 코드 → 카카오 access token. 프로필 조회에 한 번 쓰고 버린다 (저장 금지)."""
    form = {
        "grant_type": "authorization_code",
        "client_id": _client_id(),
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "code": code,
    }
    if settings.KAKAO_CLIENT_SECRET:
        form["client_secret"] = settings.KAKAO_CLIENT_SECRET
    request = Request(
        TOKEN_URL,
        data=urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        method="POST",
    )
    payload = _request_json(request)
    token = payload.get("access_token")
    if not token:
        raise KakaoError()
    return token


def fetch_profile(access_token: str) -> KakaoProfile:
    request = Request(
        PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}, method="GET"
    )
    payload = _request_json(request)
    uid = payload.get("id")
    if uid is None:
        raise KakaoError()
    account = payload.get("kakao_account") or {}
    profile = account.get("profile") or {}
    email = (account.get("email") or "").strip().lower() or None
    return KakaoProfile(
        uid=str(uid),
        email=email,
        email_verified=bool(email and account.get("is_email_verified")),
        nickname=(profile.get("nickname") or "").strip(),
        image_url=profile.get("profile_image_url") or "",
    )
