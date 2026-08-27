"""공개 인증 엔드포인트 rate limit — IP 기준.

한도 숫자는 settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] 에 scope 별로 있다.
전역(DEFAULT_THROTTLE_CLASSES)에는 걸지 않는다 — 피드 스크롤 같은 정상 사용까지
막히므로 아래 클래스를 필요한 뷰에만 붙인다.
"""

import math

from rest_framework import exceptions
from rest_framework.throttling import AnonRateThrottle


class Throttled(exceptions.Throttled):
    """DRF 기본 메시지("요청이 지연(throttled)되었습니다. Expected available in N
    seconds.")가 한·영 혼용이라 한국어 한 문장으로 바꾼다. Retry-After 헤더는
    self.wait 로 그대로 나간다."""

    def __init__(self, wait):
        self.wait = math.ceil(wait)
        super(exceptions.Throttled, self).__init__(
            detail=f"요청이 너무 많습니다. {self.wait}초 후 다시 시도해 주세요.",
            code="throttled",
        )


class ThrottledMessageMixin:
    """뷰에 섞어 쓰면 429 응답 메시지가 위 Throttled 로 바뀐다."""

    def throttled(self, request, wait):
        raise Throttled(wait)


class LoginRateThrottle(AnonRateThrottle):
    """비밀번호 무차별 대입 방지."""

    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    """봇 대량 가입 방지."""

    scope = "register"


class EmailSendRateThrottle(AnonRateThrottle):
    """인증 메일 재전송·비밀번호 재설정 요청 — 메일 폭탄 방지."""

    scope = "email_send"


class TokenConfirmRateThrottle(AnonRateThrottle):
    """토큰 확인(이메일 인증·재설정 확정) — 토큰 추측 시도 방지."""

    scope = "token_confirm"


class SocialLoginRateThrottle(AnonRateThrottle):
    """카카오 콜백 — code 는 1회용이라 추측 대상은 아니지만 카카오 API 호출을 유발한다."""

    scope = "social_login"
