"""presigned URL 발급 — boto3 는 mock, AWS 에 실제로 붙지 않는다."""

from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user

S3_SETTINGS = dict(
    AWS_ACCESS_KEY_ID="test-key",
    AWS_SECRET_ACCESS_KEY="test-secret",
    AWS_STORAGE_BUCKET_NAME="test-bucket",
    AWS_S3_REGION_NAME="ap-northeast-2",
    AWS_S3_ENDPOINT_URL=None,
    MEDIA_PUBLIC_BASE_URL="",
    S3_PRESIGNED_EXPIRE_SECONDS=300,
)


@override_settings(**S3_SETTINGS)
class PresignedUrlTests(APITestCase):
    url = reverse("v1:common:presigned-url")

    def setUp(self):
        self.user = create_verified_user()
        self.client.force_authenticate(self.user)

    def _post(self, **body):
        payload = {
            "kind": "profile_image",
            "filename": "me.jpeg",
            "content_type": "image/jpeg",
        }
        payload.update(body)
        return self.client.post(self.url, payload, format="json")

    @patch("common.services.uploads.boto3.client")
    def test_issues_presigned_put(self, client_factory):
        s3 = MagicMock()
        s3.generate_presigned_url.return_value = "https://s3.example/signed"
        client_factory.return_value = s3

        response = self._post()

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["upload_url"], "https://s3.example/signed")
        self.assertEqual(data["method"], "PUT")
        self.assertEqual(data["headers"], {"Content-Type": "image/jpeg"})
        self.assertEqual(data["expires_in"], 300)
        self.assertEqual(data["max_bytes"], 5 * 1024 * 1024)
        # 키는 {kind}/{user_id}/{uuid}{ext}, 확장자는 content_type 기준
        self.assertRegex(
            data["key"], rf"^profile_image/{self.user.pk}/[0-9a-f]{{32}}\.jpg$"
        )
        self.assertEqual(
            data["file_url"],
            f"https://test-bucket.s3.ap-northeast-2.amazonaws.com/{data['key']}",
        )

        s3.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": "test-bucket",
                "Key": data["key"],
                "ContentType": "image/jpeg",
            },
            ExpiresIn=300,
            HttpMethod="PUT",
        )
        _, kwargs = client_factory.call_args
        self.assertEqual(kwargs["region_name"], "ap-northeast-2")
        self.assertEqual(kwargs["aws_access_key_id"], "test-key")

    @patch("common.services.uploads.boto3.client")
    def test_video_kind_and_extension_from_content_type(self, client_factory):
        client_factory.return_value.generate_presigned_url.return_value = "https://x"
        # 파일명 확장자(.avi)가 아니라 content_type(quicktime → .mov) 을 따른다.
        response = self._post(
            kind="climb_video", filename="clip.avi", content_type="video/quicktime"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["key"].startswith(f"climb_video/{self.user.pk}/"))
        self.assertTrue(data["key"].endswith(".mov"))
        self.assertEqual(data["max_bytes"], 200 * 1024 * 1024)

    @patch("common.services.uploads.boto3.client")
    @override_settings(MEDIA_PUBLIC_BASE_URL="https://cdn.example.com/")
    def test_file_url_uses_cdn_base_when_set(self, client_factory):
        client_factory.return_value.generate_presigned_url.return_value = "https://x"
        data = self._post(kind="post_image").json()["data"]
        self.assertEqual(data["file_url"], f"https://cdn.example.com/{data['key']}")
        self.assertEqual(data["max_bytes"], 10 * 1024 * 1024)

    @patch("common.services.uploads.boto3.client")
    @override_settings(AWS_S3_ENDPOINT_URL="http://minio:9000")
    def test_file_url_is_path_style_for_custom_endpoint(self, client_factory):
        client_factory.return_value.generate_presigned_url.return_value = "https://x"
        data = self._post().json()["data"]
        self.assertEqual(
            data["file_url"], f"http://minio:9000/test-bucket/{data['key']}"
        )
        self.assertEqual(
            client_factory.call_args.kwargs["endpoint_url"], "http://minio:9000"
        )

    @patch("common.services.uploads.boto3.client")
    def test_rejects_unknown_kind(self, client_factory):
        response = self._post(kind="avatar")
        self.assertEqual(response.status_code, 400)
        self.assertIn("kind", response.json()["error"]["fields"])
        client_factory.assert_not_called()

    @patch("common.services.uploads.boto3.client")
    def test_rejects_content_type_not_allowed_for_kind(self, client_factory):
        response = self._post(kind="profile_image", content_type="video/mp4")
        self.assertEqual(response.status_code, 400)
        self.assertIn("content_type", response.json()["error"]["fields"])

        response = self._post(kind="climb_video", content_type="image/png")
        self.assertEqual(response.status_code, 400)

        response = self._post(content_type="image/gif")
        self.assertEqual(response.status_code, 400)
        client_factory.assert_not_called()

    def test_requires_all_fields(self):
        response = self.client.post(self.url, {"kind": "profile_image"}, format="json")
        self.assertEqual(response.status_code, 400)
        fields = response.json()["error"]["fields"]
        self.assertIn("filename", fields)
        self.assertIn("content_type", fields)

    @patch("common.services.uploads.boto3.client")
    @override_settings(AWS_STORAGE_BUCKET_NAME="")
    def test_503_when_bucket_not_configured(self, client_factory):
        response = self._post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "storage_not_configured")
        client_factory.assert_not_called()

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        response = self._post()
        self.assertEqual(response.status_code, 401)
