from rest_framework import status
from rest_framework.exceptions import APIException


class EmailNotVerified(APIException):
    """비밀번호는 맞지만 이메일 인증이 안 된 계정의 로그인 시도."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "이메일 인증이 필요합니다. 메일함을 확인해 주세요."
    default_code = "email_not_verified"


class InvalidToken(APIException):
    """이메일 인증/비밀번호 재설정 링크가 위조·만료·이미 사용됨."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "링크가 유효하지 않거나 만료되었습니다. 다시 요청해 주세요."
    default_code = "invalid_token"


class UserInactive(APIException):
    """refresh 토큰의 주인이 탈퇴(soft delete)했거나 비활성화됨."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "사용할 수 없는 계정입니다. 다시 로그인해 주세요."
    default_code = "user_inactive"
