from rest_framework import status
from rest_framework.exceptions import APIException


class CrewFull(APIException):
    """활동 중인 크루원이 이미 최대 인원이다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "크루 정원이 모두 찼습니다."
    default_code = "crew_full"


class AlreadyMember(APIException):
    """이미 소속(활동 중/승인 대기)인 크루에 다시 가입 신청했다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "이미 가입했거나 승인 대기 중인 크루입니다."
    default_code = "already_member"


class OwnerCannotLeave(APIException):
    """크루장은 탈퇴할 수 없다 (크루 삭제만 가능)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "크루장은 탈퇴할 수 없습니다. 크루를 삭제해 주세요."
    default_code = "owner_cannot_leave"


class NotCrewMember(APIException):
    """활동 중인 크루원이 아니다 (탈퇴 시도, 크루 주최 모집 작성 등)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "가입한 크루가 아닙니다."
    default_code = "not_crew_member"


class CannotChangeOwner(APIException):
    """크루장의 역할은 바꿀 수 없다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "크루장의 역할은 변경할 수 없습니다."
    default_code = "cannot_change_owner"
