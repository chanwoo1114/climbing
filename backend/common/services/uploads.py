"""S3 presigned URL 발급 — 파일은 서버를 거치지 않고 클라이언트가 직접 올린다.

presigned PUT 을 쓴다 (presigned POST 보다 프론트가 단순: fetch(url, {method: "PUT",
headers, body: file})). PUT 은 서명에 Content-Length 조건을 못 넣으므로 max_bytes 는
클라이언트 사전 검사용 힌트다. 서버 측 강제는 버킷 정책/후처리에서 한다.
"""

import uuid
from dataclasses import dataclass

import boto3
from botocore.config import Config
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

MB = 1024 * 1024

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}


@dataclass(frozen=True)
class UploadKind:
    # content_type → 확장자. 확장자는 파일명이 아니라 content_type 에서 정한다.
    content_types: dict[str, str]
    max_bytes: int


UPLOAD_KINDS: dict[str, UploadKind] = {
    "profile_image": UploadKind(IMAGE_TYPES, 5 * MB),
    "post_image": UploadKind(IMAGE_TYPES, 10 * MB),
    "climb_video": UploadKind(VIDEO_TYPES, 200 * MB),
    "beta_video": UploadKind(VIDEO_TYPES, 200 * MB),
    "beta_thumbnail": UploadKind(IMAGE_TYPES, 5 * MB),
}


class StorageNotConfigured(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "파일 저장소가 설정되지 않았습니다."
    default_code = "storage_not_configured"


def allowed_content_types(kind: str) -> set[str]:
    return set(UPLOAD_KINDS[kind].content_types)


def build_key(*, kind: str, user_id: int, content_type: str) -> str:
    """{kind}/{user_id}/{uuid}{ext}"""
    ext = UPLOAD_KINDS[kind].content_types[content_type]
    return f"{kind}/{user_id}/{uuid.uuid4().hex}{ext}"


def public_file_url(key: str) -> str:
    """업로드 완료 후 DB 에 저장할 공개 URL."""
    if settings.MEDIA_PUBLIC_BASE_URL:
        return f"{settings.MEDIA_PUBLIC_BASE_URL.rstrip('/')}/{key}"
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    if settings.AWS_S3_ENDPOINT_URL:
        # MinIO / R2 는 path-style.
        return f"{settings.AWS_S3_ENDPOINT_URL.rstrip('/')}/{bucket}/{key}"
    return f"https://{bucket}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{key}"


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        config=Config(signature_version="s3v4"),
    )


def create_presigned_upload(*, user_id: int, kind: str, content_type: str) -> dict:
    """presigned PUT URL 과 클라이언트가 그대로 보내야 하는 헤더를 돌려준다."""
    if not settings.AWS_STORAGE_BUCKET_NAME:
        raise StorageNotConfigured()

    spec = UPLOAD_KINDS[kind]
    key = build_key(kind=kind, user_id=user_id, content_type=content_type)
    expires_in = settings.S3_PRESIGNED_EXPIRE_SECONDS

    upload_url = _s3_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )
    return {
        "upload_url": upload_url,
        "method": "PUT",
        # 서명에 포함된 값 — 클라이언트가 다른 Content-Type 을 보내면 403.
        "headers": {"Content-Type": content_type},
        "file_url": public_file_url(key),
        "key": key,
        "expires_in": expires_in,
        "max_bytes": spec.max_bytes,
    }
