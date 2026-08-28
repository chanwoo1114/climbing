from rest_framework import status
from rest_framework.exceptions import APIException


class LastManager(APIException):
    """마지막 남은 암장 관리자는 해제할 수 없다 (운영자 is_staff 만 가능)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "마지막 관리자는 해제할 수 없습니다. 다른 관리자를 먼저 추가해 주세요."
    )
    default_code = "last_manager"
