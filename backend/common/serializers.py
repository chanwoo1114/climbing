from rest_framework import serializers

from common.services.uploads import UPLOAD_KINDS, allowed_content_types


class PresignedUrlRequestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=sorted(UPLOAD_KINDS),
        error_messages={"invalid_choice": "지원하지 않는 업로드 종류입니다."},
    )
    # 확장자는 content_type 으로 정하므로 filename 은 검증·로그 용도로만 받는다.
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)

    def validate(self, attrs):
        allowed = allowed_content_types(attrs["kind"])
        if attrs["content_type"] not in allowed:
            raise serializers.ValidationError(
                {
                    "content_type": (
                        f"{attrs['kind']} 에 허용되지 않는 형식입니다. "
                        f"허용: {', '.join(sorted(allowed))}"
                    )
                }
            )
        return attrs


class PresignedUrlResponseSerializer(serializers.Serializer):
    """스키마 문서용. 실제 값은 services.uploads.create_presigned_upload 가 만든다."""

    upload_url = serializers.URLField()
    method = serializers.CharField()
    headers = serializers.DictField(child=serializers.CharField())
    file_url = serializers.URLField()
    key = serializers.CharField()
    expires_in = serializers.IntegerField()
    max_bytes = serializers.IntegerField()
