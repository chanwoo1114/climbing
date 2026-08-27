from rest_framework import status
from rest_framework.exceptions import APIException


class RecruitmentFull(APIException):
    """정원(작성자 포함)이 이미 찼다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "모집 정원이 모두 찼습니다."
    default_code = "recruitment_full"


class RecruitmentClosed(APIException):
    """마감·취소된 모집에 참여/승인/마감을 시도했다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "이미 마감된 모집입니다."
    default_code = "recruitment_closed"


class AlreadyJoined(APIException):
    """이미 참여(대기/승인/거절) 중인 모집에 다시 참여했다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "이미 참여 신청한 모집입니다."
    default_code = "already_joined"


class OwnRecruitment(APIException):
    """작성자가 자기 모집에 참여했다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "본인이 작성한 모집에는 참여할 수 없습니다."
    default_code = "own_recruitment"


class NotParticipating(APIException):
    """참여 중이 아닌데 취소했다."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "참여 중인 모집이 아닙니다."
    default_code = "not_participating"
