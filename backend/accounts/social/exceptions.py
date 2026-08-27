from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidState(APIException):
    """authorize 에서 발급한 state 가 위조·만료됨 (KAKAO_STATE_TIMEOUT)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "로그인 요청이 만료되었거나 올바르지 않습니다. 다시 시도해 주세요."
    default_code = "invalid_state"


class KakaoError(APIException):
    """카카오 토큰 교환 / 프로필 조회 실패 (네트워크, 잘못된 code, 키 오류)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "카카오 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요."
    default_code = "kakao_error"


class KakaoNotConfigured(APIException):
    """KAKAO_CLIENT_ID 가 비어 있음."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "카카오 로그인이 설정되지 않았습니다."
    default_code = "kakao_not_configured"


class EmailConflict(APIException):
    """같은 이메일의 기존 계정이 있지만 카카오 쪽 이메일이 미인증이라 자동 연결 불가."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "같은 이메일로 가입된 계정이 있습니다. 비밀번호로 로그인한 뒤 "
        "설정에서 카카오 계정을 연결해 주세요."
    )
    default_code = "email_conflict"


class LastLoginMethod(APIException):
    """비밀번호가 없는 계정의 유일한 소셜 연결은 해제할 수 없다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = (
        "유일한 로그인 수단은 해제할 수 없습니다. 비밀번호를 먼저 설정해 주세요."
    )
    default_code = "last_login_method"
