from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.serializers import (
    PresignedUrlRequestSerializer,
    PresignedUrlResponseSerializer,
)
from common.services.uploads import create_presigned_upload


@extend_schema(
    tags=["uploads"],
    request=PresignedUrlRequestSerializer,
    responses=PresignedUrlResponseSerializer,
)
class PresignedUrlView(APIView):
    """S3 presigned PUT URL 발급. 파일은 클라이언트가 S3 로 직접 올린다.

    클라이언트는 upload_url 로 PUT 하되 headers 에 담긴 Content-Type 을 그대로
    보내야 서명이 맞는다. 업로드 후 file_url 을 프로필/로그 API 에 저장한다.
    """

    def post(self, request):
        serializer = PresignedUrlRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = create_presigned_upload(
            user_id=request.user.pk,
            kind=serializer.validated_data["kind"],
            content_type=serializer.validated_data["content_type"],
        )
        return Response(data)


class HealthView(APIView):
    """컨테이너 헬스체크용. 공개 엔드포인트."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok"})
