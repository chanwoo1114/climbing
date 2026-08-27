"""analyses/ API — 요청(작성자만, 영상 필수, 기록당 1건), 조회 권한(작성자 또는 공개 기록)."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from analysis.models import VideoAnalysis
from analysis.tests.helpers import VIDEO_URL, create_analysis, make_keypoints
from climbs.tests.helpers import create_gym, create_log


class VideoAnalysisRequestTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.other = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym, video_url=VIDEO_URL)
        cls.no_video = create_log(cls.owner, cls.gym, video_url="")
        cls.url = reverse("v1:analysis:analysis-list")

    def setUp(self):
        self.client.force_authenticate(self.owner)
        patcher = patch("analysis.tasks.analyze_video.delay")
        self.delay = patcher.start()
        self.delay.return_value.id = "task-123"
        self.addCleanup(patcher.stop)

    def _request(self, log):
        # 큐잉은 transaction.on_commit 이라 커밋 콜백을 실행해 줘야 한다.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {"climb_log": log.id})

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        response = self.client.post(self.url, {"climb_log": self.log.id})
        self.assertEqual(response.status_code, 401)
        self.delay.assert_not_called()

    def test_request_creates_pending_analysis_and_enqueues(self):
        response = self._request(self.log)
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertTrue(body["success"])
        data = body["data"]
        self.assertEqual(data["climb_log"], self.log.id)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["error_message"], "")
        self.assertEqual(data["metrics"], {})
        self.assertNotIn("keypoints", data)

        analysis = VideoAnalysis.objects.get(pk=data["id"])
        self.delay.assert_called_once_with(analysis.id)
        self.assertEqual(analysis.task_id, "task-123")

    def test_only_owner_can_request(self):
        self.client.force_authenticate(self.other)
        response = self._request(self.log)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "permission_denied")
        self.assertFalse(VideoAnalysis.objects.filter(climb_log=self.log).exists())
        self.delay.assert_not_called()

    def test_video_required(self):
        response = self._request(self.no_video)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "video_required")
        self.delay.assert_not_called()

    def test_unknown_log(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {"climb_log": 999999})
        self.assertEqual(response.status_code, 400)
        self.assertIn("climb_log", response.json()["error"]["fields"])
        self.delay.assert_not_called()

    def test_existing_analysis_is_returned_without_requeue(self):
        existing = create_analysis(
            self.log, status=VideoAnalysis.Status.PROCESSING, task_id="old"
        )
        response = self._request(self.log)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], existing.id)
        self.assertEqual(response.json()["data"]["status"], "processing")
        self.delay.assert_not_called()
        self.assertEqual(VideoAnalysis.objects.filter(climb_log=self.log).count(), 1)

    def test_done_analysis_is_returned_without_requeue(self):
        existing = create_analysis(
            self.log, status=VideoAnalysis.Status.DONE, metrics={"duration": 3}
        )
        response = self._request(self.log)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], existing.id)
        self.assertEqual(response.json()["data"]["metrics"], {"duration": 3})
        self.delay.assert_not_called()

    def test_failed_analysis_is_reset_and_requeued(self):
        failed = create_analysis(
            self.log,
            status=VideoAnalysis.Status.FAILED,
            error_message="영상을 내려받지 못했습니다.",
            retry_count=1,
            task_id="old",
        )
        response = self._request(self.log)
        self.assertEqual(response.status_code, 202)
        data = response.json()["data"]
        self.assertEqual(data["id"], failed.id)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["error_message"], "")
        self.assertEqual(data["retry_count"], 0)
        self.delay.assert_called_once_with(failed.id)
        failed.refresh_from_db()
        self.assertEqual(failed.task_id, "task-123")

    def test_soft_deleted_analysis_is_restored(self):
        old = create_analysis(self.log, status=VideoAnalysis.Status.DONE)
        old.delete()
        self.assertFalse(VideoAnalysis.objects.filter(pk=old.pk).exists())

        response = self._request(self.log)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["id"], old.id)
        self.assertTrue(VideoAnalysis.objects.filter(pk=old.pk).exists())
        self.delay.assert_called_once_with(old.id)


class VideoAnalysisReadTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.other = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.shared_log = create_log(cls.owner, cls.gym, video_url=VIDEO_URL)
        cls.private_log = create_log(
            cls.owner, cls.gym, video_url=VIDEO_URL, is_shared=False
        )
        keypoints = make_keypoints(seconds=1.0)
        cls.shared = create_analysis(
            cls.shared_log,
            status=VideoAnalysis.Status.DONE,
            keypoints=keypoints,
            metrics={"duration": 1.0},
        )
        cls.private = create_analysis(cls.private_log)
        cls.list_url = reverse("v1:analysis:analysis-list")

    @staticmethod
    def _detail(analysis):
        return reverse("v1:analysis:analysis-detail", args=[analysis.id])

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self._detail(self.shared)).status_code, 401)
        self.assertEqual(self.client.get(self.list_url).status_code, 401)

    def test_owner_reads_own_analysis_without_keypoints(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self._detail(self.private))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], "pending")
        self.assertNotIn("keypoints", data)

    def test_include_keypoints(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self._detail(self.shared), {"include": "keypoints"})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["metrics"], {"duration": 1.0})
        self.assertEqual(len(data["keypoints"]["frames"]), 10)
        self.assertEqual(len(data["keypoints"]["frames"][0]["lm"]), 33)

    def test_other_user_reads_shared_log_analysis(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(self._detail(self.shared))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], self.shared.id)

    def test_other_user_cannot_read_private_log_analysis(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self._detail(self.private)).status_code, 404)

    def test_unknown_analysis(self):
        self.client.force_authenticate(self.owner)
        url = reverse("v1:analysis:analysis-detail", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_list_filters_by_visibility(self):
        self.client.force_authenticate(self.other)
        ids = [
            row["id"]
            for row in self.client.get(self.list_url).json()["data"]["results"]
        ]
        self.assertEqual(ids, [self.shared.id])

        self.client.force_authenticate(self.owner)
        ids = [
            row["id"]
            for row in self.client.get(self.list_url).json()["data"]["results"]
        ]
        self.assertCountEqual(ids, [self.shared.id, self.private.id])

    def test_list_lookup_by_climb_log(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.list_url, {"climb_log": self.private_log.id})
        results = response.json()["data"]["results"]
        self.assertEqual([row["id"] for row in results], [self.private.id])
        self.assertNotIn("keypoints", results[0])

        self.client.force_authenticate(self.other)
        response = self.client.get(self.list_url, {"climb_log": self.private_log.id})
        self.assertEqual(response.json()["data"]["results"], [])

    def test_deleted_log_hides_analysis(self):
        self.client.force_authenticate(self.owner)
        self.shared_log.delete()  # soft delete → analysis 도 cascade
        self.assertEqual(self.client.get(self._detail(self.shared)).status_code, 404)
