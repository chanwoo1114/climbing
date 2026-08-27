from rest_framework import status
from rest_framework.exceptions import APIException


class SelfFollowNotAllowed(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "자기 자신은 팔로우할 수 없습니다."
    default_code = "self_follow"
