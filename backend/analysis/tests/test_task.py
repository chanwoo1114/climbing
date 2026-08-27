"""analyze_video 태스크 흐름 — extract_keypoints/download_video 를 mock 해 영상 없이 검증.

테스트 설정은 CELERY_TASK_ALWAYS_EAGER 라 .delay() 가 그 자리에서 실행된다.
재시도(self.retry)는 apply(throw=False) 로 돌리면 eager 모드에서도 retries+1 로 즉시 재실행된다.
"""

from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from accounts.tests.helpers import create_verified_user
from analysis.models import VideoAnalysis
from analysis.pipeline import ERROR_MESSAGES, AnalysisError
from analysis.tasks import analyze_video
from analysis.tests.helpers import VIDEO_URL, create_analysis, make_keypoints
from climbs.tests.helpers import create_gym, create_log

FAKE_PATH = Path("/tmp/fake-video.mp4")


class AnalyzeVideoTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_verified_user()
        cls.gym = create_gym()

    def setUp(self):
        self.log = create_log(self.user, self.gym, video_url=VIDEO_URL)
        self.analysis = create_analysis(self.log)

        download = patch("analysis.pipeline.download_video", return_value=FAKE_PATH)
        extract = patch(
            "analysis.pipeline.extract_keypoints", return_value=make_keypoints()
        )
        self.download = download.start()
        self.extract = extract.start()
        self.addCleanup(download.stop)
        self.addCleanup(extract.stop)

    def _run(self):
        result = analyze_video.delay(self.analysis.id)
        self.analysis.refresh_from_db()
        return result

    def _run_with_retries(self):
        """재시도 경로용. eager + task_eager_propagates 에서는 self.retry() 의 Retry 가
        호출자에게 그대로 던져지므로, throw=False 로 워커처럼 retries+1 재실행되게 한다."""
        result = analyze_video.apply(args=(self.analysis.id,), throw=False)
        self.analysis.refresh_from_db()
        return result

    def test_success_saves_keypoints_and_metrics(self):
        result = self._run()
        self.assertEqual(result.get(), "done")
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.DONE)
        self.assertIsNotNone(self.analysis.processed_at)
        self.assertEqual(self.analysis.error_message, "")
        self.assertEqual(self.analysis.retry_count, 0)
        self.assertEqual(len(self.analysis.keypoints["frames"]), 60)
        self.assertAlmostEqual(
            self.analysis.metrics["com"]["vertical_gain"], 0.3, places=2
        )
        self.assertIn("left_elbow", self.analysis.metrics["joint_angles"])

        self.download.assert_called_once()
        self.assertEqual(self.download.call_args.args[0], VIDEO_URL)
        self.extract.assert_called_once_with(FAKE_PATH)

    def test_video_required_when_log_has_no_video(self):
        self.log.video_url = ""
        self.log.save(update_fields=["video_url", "updated_at"])

        self._run()
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.FAILED)
        self.assertEqual(self.analysis.error_message, ERROR_MESSAGES["video_required"])
        self.download.assert_not_called()
        self.extract.assert_not_called()

    def test_video_too_long_fails_without_retry(self):
        self.extract.side_effect = AnalysisError(
            "video_too_long", "영상은 최대 120초까지 분석할 수 있습니다."
        )
        self._run()
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.FAILED)
        self.assertIn("최대 120초", self.analysis.error_message)
        self.assertEqual(self.analysis.retry_count, 0)
        self.assertEqual(self.analysis.metrics, {})
        self.extract.assert_called_once()

    def test_no_pose_detected_fails(self):
        self.extract.return_value = make_keypoints(
            seconds=1.0, undetected=set(range(10))
        )
        self._run()
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.FAILED)
        self.assertEqual(
            self.analysis.error_message, ERROR_MESSAGES["no_pose_detected"]
        )

    def test_unexpected_exception_fails_with_generic_message(self):
        self.extract.side_effect = RuntimeError("boom: /tmp/secret/path")
        self._run()
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.FAILED)
        self.assertEqual(self.analysis.error_message, ERROR_MESSAGES["unknown"])
        self.assertNotIn("secret", self.analysis.error_message)

    def test_retryable_error_is_retried_once_then_succeeds(self):
        self.download.side_effect = [
            AnalysisError("download_failed", retryable=True),
            FAKE_PATH,
        ]
        self._run_with_retries()
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.DONE)
        self.assertEqual(self.analysis.retry_count, 1)
        self.assertEqual(self.download.call_count, 2)
        self.extract.assert_called_once()

    def test_retryable_error_twice_fails(self):
        self.download.side_effect = AnalysisError("download_failed", retryable=True)
        self._run_with_retries()
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.FAILED)
        self.assertEqual(self.analysis.error_message, ERROR_MESSAGES["download_failed"])
        self.assertEqual(self.analysis.retry_count, 1)  # 최대 1회만 재시도
        self.assertEqual(self.download.call_count, 2)
        self.extract.assert_not_called()

    def test_non_retryable_download_error_is_not_retried(self):
        self.download.side_effect = AnalysisError("video_too_large")
        self._run()
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.FAILED)
        self.assertEqual(self.analysis.error_message, ERROR_MESSAGES["video_too_large"])
        self.assertEqual(self.analysis.retry_count, 0)
        self.assertEqual(self.download.call_count, 1)

    def test_missing_analysis_is_ignored(self):
        result = analyze_video.delay(999999)
        self.assertEqual(result.get(), "missing")
        self.extract.assert_not_called()

    def test_done_analysis_is_not_reprocessed(self):
        self.analysis.status = VideoAnalysis.Status.DONE
        self.analysis.metrics = {"duration": 9}
        self.analysis.save()
        result = self._run()
        self.assertEqual(result.get(), "done")
        self.assertEqual(self.analysis.metrics, {"duration": 9})
        self.extract.assert_not_called()

    def test_processing_status_is_set_before_pipeline(self):
        seen = {}

        def capture(path):
            seen["status"] = VideoAnalysis.objects.get(pk=self.analysis.pk).status
            return make_keypoints()

        self.extract.side_effect = capture
        self._run()
        self.assertEqual(seen["status"], VideoAnalysis.Status.PROCESSING)
        self.assertEqual(self.analysis.status, VideoAnalysis.Status.DONE)
