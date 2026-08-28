from rest_framework import status
from rest_framework.exceptions import APIException


class PushNotConfigured(APIException):
    """WEBPUSH_VAPID_PUBLIC_KEY / PRIVATE_KEY 가 비어 있음 — 구독 등록·공개키 조회 불가."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "푸시 알림이 설정되지 않았습니다."
    default_code = "push_not_configured"
