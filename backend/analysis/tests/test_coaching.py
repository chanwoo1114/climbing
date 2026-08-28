"""AI 코칭 리포트 — POST analyses/{id}/report/ 와 generate_coaching_report 태스크.

LLM 호출은 `analysis.coaching._client` 를 mock 한다 (실제 API 호출 없음).
테스트 설정은 CELERY_TASK_ALWAYS_EAGER 라 captureOnCommitCallbacks(execute=True) 안에서
POST 하면 태스크가 그 자리에서 끝까지 돈다.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx2 as httpx
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from analysis import coaching
from analysis.models import VideoAnalysis
from analysis.pipeline import compute_metrics
from analysis.tasks import generate_coaching_report
from analysis.tests.helpers import VIDEO_URL, create_analysis, make_keypoints
from climbs.tests.helpers import create_difficulty, create_gym, create_log

REPORT_TEXT = "## 한눈에 보기\n안정적인 등반이었습니다.\n\n## 잘한 점\n- 정적 구간 유지"
GYM_NAME = "코칭테스트암장"


def fake_response(text=REPORT_TEXT, stop_reason="end_turn", **overrides):
    data = {
        "content": [SimpleNamespace(type="text", text=text)],
        "stop_reason": stop_reason,
        "model": "claude-opus-5",
        "usage": SimpleNamespace(input_tokens=100, output_tokens=200),
        "stop_details": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def api_status_error(cls, status_code: int, message: str = "error"):
    """SDK 상태 오류 인스턴스 — httpx2 응답을 붙여 실제 생성자로 만든다."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    return cls(message, response=response, body=None)


def connection_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


class CoachingTestMixin:
    """_client mock + done 상태 분석 픽스처."""

    def start_client_mock(self):
        patcher = patch("analysis.coaching._client")
        client_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.client_mock = MagicMock()
        client_factory.return_value = self.client_mock
        self.create = self.client_mock.messages.create
        self.create.return_value = fake_response()

    @staticmethod
    def make_done_analysis(log):
        keypoints = make_keypoints(seconds=2.0)
        return create_analysis(
            log,
            status=VideoAnalysis.Status.DONE,
            keypoints=keypoints,
            metrics=compute_metrics(keypoints),
        )


@override_settings(
    ANTHROPIC_API_KEY="test-key",
    COACHING_MODEL="claude-opus-5",
    COACHING_MAX_TOKENS=4096,
    COACHING_EFFORT="medium",
)
class CoachingReportApiTests(CoachingTestMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.other = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym(name=GYM_NAME)
        cls.difficulty = create_difficulty(cls.gym, name="파랑", order=3)

    def setUp(self):
        self.client.force_authenticate(self.owner)
        self.start_client_mock()
        self.log = create_log(
            self.owner,
            self.gym,
            video_url=VIDEO_URL,
            difficulty=self.difficulty,
            memo="발이 자꾸 빠짐",
        )
        self.analysis = self.make_done_analysis(self.log)

    @staticmethod
    def _url(analysis):
        return reverse("v1:analysis:analysis-report", args=[analysis.id])

    def _post(self, analysis):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self._url(analysis))

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        response = self.client.post(self._url(self.analysis))
        self.assertEqual(response.status_code, 401)
        self.create.assert_not_called()

    def test_non_owner_gets_404(self):
        self.client.force_authenticate(self.other)
        response = self._post(self.analysis)
        self.assertEqual(response.status_code, 404)
        self.create.assert_not_called()
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.report_status, "none")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_503_when_not_configured(self):
        response = self._post(self.analysis)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "coaching_not_configured")
        self.create.assert_not_called()

    def test_409_when_analysis_not_done(self):
        pending = create_analysis(create_log(self.owner, self.gym, video_url=VIDEO_URL))
        response = self._post(pending)
        self.assertEqual(response.status_code, 409)
        body = response.json()["error"]
        self.assertEqual(body["code"], "analysis_not_done")
        self.assertEqual(
            body["message"], "자세 분석이 완료된 뒤 리포트를 만들 수 있습니다."
        )
        self.create.assert_not_called()

    def test_409_when_report_already_pending(self):
        self.analysis.report_status = VideoAnalysis.ReportStatus.PENDING
        self.analysis.save()
        response = self._post(self.analysis)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "report_in_progress")
        self.create.assert_not_called()

    def test_202_generates_and_saves_report(self):
        response = self._post(self.analysis)
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertTrue(body["success"])
        data = body["data"]
        self.assertEqual(data["id"], self.analysis.id)
        # 응답은 큐잉 직후 스냅샷 (eager 라 DB 는 이미 done)
        self.assertEqual(data["report_status"], "pending")
        self.assertNotIn("keypoints", data)

        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.report_status, "done")
        self.assertEqual(self.analysis.report, REPORT_TEXT)
        self.assertEqual(self.analysis.report_model, "claude-opus-5")
        self.assertEqual(self.analysis.report_input_tokens, 100)
        self.assertEqual(self.analysis.report_output_tokens, 200)
        self.assertIsNotNone(self.analysis.report_generated_at)
        self.assertEqual(self.analysis.report_error, "")
        self.assertTrue(self.analysis.report_task_id)

        detail = self.client.get(
            reverse("v1:analysis:analysis-detail", args=[self.analysis.id])
        )
        data = detail.json()["data"]
        self.assertEqual(data["report_status"], "done")
        self.assertEqual(data["report"], REPORT_TEXT)
        self.assertEqual(data["report_output_tokens"], 200)

    def test_prompt_and_request_parameters(self):
        self._post(self.analysis)
        self.create.assert_called_once()
        kwargs = self.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5")
        self.assertEqual(kwargs["max_tokens"], 4096)
        self.assertEqual(kwargs["output_config"], {"effort": "medium"})
        self.assertEqual(kwargs["system"], coaching.SYSTEM_PROMPT)
        for forbidden in ("thinking", "temperature", "top_p", "budget_tokens"):
            self.assertNotIn(forbidden, kwargs)

        messages = kwargs["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        prompt = messages[0]["content"]
        self.assertIn(GYM_NAME, prompt)
        self.assertIn('"name": "파랑"', prompt)
        self.assertIn('"order": 3', prompt)
        self.assertIn("발이 자꾸 빠짐", prompt)
        self.assertIn('"is_success": true', prompt)
        self.assertIn('"attempts": 2', prompt)
        metrics = self.analysis.metrics
        self.assertIn(f'"vertical_gain": {metrics["com"]["vertical_gain"]}', prompt)
        self.assertIn(f'"duration": {metrics["duration"]}', prompt)
        self.assertIn("left_elbow", prompt)
        self.assertIn("move_ratio", prompt)
        self.assertIn("용어집", prompt)

    def test_refusal_marks_failed(self):
        self.create.return_value = fake_response(
            text="", stop_reason="refusal", stop_details=None
        )
        response = self._post(self.analysis)
        self.assertEqual(response.status_code, 202)
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(
            self.analysis.report_error, "리포트를 생성할 수 없는 내용입니다."
        )
        self.assertEqual(self.analysis.report, "")

    def test_regenerate_allowed_after_done_and_failed(self):
        self._post(self.analysis)
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.report_status, "done")

        self.create.return_value = fake_response(text="## 한눈에 보기\n두 번째 리포트")
        response = self._post(self.analysis)
        self.assertEqual(response.status_code, 202)
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.report, "## 한눈에 보기\n두 번째 리포트")
        self.assertEqual(self.create.call_count, 2)

        VideoAnalysis.objects.filter(pk=self.analysis.pk).update(
            report_status=VideoAnalysis.ReportStatus.FAILED, report_error="x"
        )
        response = self._post(self.analysis)
        self.assertEqual(response.status_code, 202)
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.report_status, "done")
        self.assertEqual(self.analysis.report_error, "")
        self.assertEqual(self.create.call_count, 3)


@override_settings(ANTHROPIC_API_KEY="test-key")
class GenerateCoachingReportTaskTests(CoachingTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_verified_user()
        cls.gym = create_gym(name=GYM_NAME)

    def setUp(self):
        self.start_client_mock()
        self.log = create_log(self.user, self.gym, video_url=VIDEO_URL)
        self.analysis = self.make_done_analysis(self.log)
        self.analysis.report_status = VideoAnalysis.ReportStatus.PENDING
        self.analysis.save()

    def _run(self):
        """워커처럼 실행 — throw=False 라 self.retry() 가 retries+1 로 즉시 재실행된다."""
        result = generate_coaching_report.apply(args=(self.analysis.id,), throw=False)
        self.analysis.refresh_from_db()
        return result

    def test_success(self):
        result = self._run()
        self.assertEqual(result.get(), "done")
        self.assertEqual(self.analysis.report_status, "done")
        self.assertEqual(self.analysis.report, REPORT_TEXT)
        self.assertEqual(self.analysis.retry_count, 0)

    def test_rate_limit_is_retried_once_then_failed(self):
        self.create.side_effect = api_status_error(anthropic.RateLimitError, 429)
        self._run()
        self.assertEqual(self.create.call_count, 2)
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(
            self.analysis.report_error, coaching.ERROR_MESSAGES["rate_limit"]
        )
        self.assertEqual(self.analysis.retry_count, 0)  # 자세 분석 재시도 수는 그대로

    def test_rate_limit_then_success(self):
        self.create.side_effect = [
            api_status_error(anthropic.RateLimitError, 429),
            fake_response(),
        ]
        self._run()
        self.assertEqual(self.create.call_count, 2)
        self.assertEqual(self.analysis.report_status, "done")
        self.assertEqual(self.analysis.report, REPORT_TEXT)

    def test_server_error_and_connection_error_are_retryable(self):
        self.create.side_effect = api_status_error(anthropic.InternalServerError, 500)
        self._run()
        self.assertEqual(self.create.call_count, 2)
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(self.analysis.report_error, coaching.ERROR_MESSAGES["server"])

        self.create.reset_mock()
        self.create.side_effect = connection_error()
        VideoAnalysis.objects.filter(pk=self.analysis.pk).update(
            report_status=VideoAnalysis.ReportStatus.PENDING
        )
        self._run()
        self.assertEqual(self.create.call_count, 2)
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(
            self.analysis.report_error, coaching.ERROR_MESSAGES["connection"]
        )

    def test_authentication_error_is_not_retried(self):
        self.create.side_effect = api_status_error(anthropic.AuthenticationError, 401)
        self._run()
        self.assertEqual(self.create.call_count, 1)
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(self.analysis.report_error, coaching.ERROR_MESSAGES["auth"])

    def test_bad_request_is_not_retried(self):
        self.create.side_effect = api_status_error(anthropic.BadRequestError, 400)
        self._run()
        self.assertEqual(self.create.call_count, 1)
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(
            self.analysis.report_error, coaching.ERROR_MESSAGES["bad_request"]
        )

    def test_empty_text_marks_failed(self):
        self.create.return_value = fake_response(text="   ")
        self._run()
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(self.analysis.report_error, coaching.ERROR_MESSAGES["empty"])

    def test_max_tokens_saves_text_with_note(self):
        self.create.return_value = fake_response(stop_reason="max_tokens")
        self._run()
        self.assertEqual(self.analysis.report_status, "done")
        self.assertTrue(self.analysis.report.startswith(REPORT_TEXT))
        self.assertIn("길이 제한", self.analysis.report)

    def test_unexpected_exception_fails_with_generic_message(self):
        self.create.side_effect = RuntimeError("boom: secret")
        result = self._run()
        self.assertEqual(result.get(), "failed")
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertEqual(self.analysis.report_error, coaching.ERROR_MESSAGES["unknown"])
        self.assertNotIn("secret", self.analysis.report_error)

    def test_analysis_not_done_fails(self):
        VideoAnalysis.objects.filter(pk=self.analysis.pk).update(
            status=VideoAnalysis.Status.FAILED
        )
        result = self._run()
        self.assertEqual(result.get(), "failed")
        self.assertEqual(self.analysis.report_status, "failed")
        self.assertIn("자세 분석이 완료된 뒤", self.analysis.report_error)
        self.create.assert_not_called()

    def test_skips_when_not_requested(self):
        VideoAnalysis.objects.filter(pk=self.analysis.pk).update(
            report_status=VideoAnalysis.ReportStatus.NONE
        )
        result = self._run()
        self.assertEqual(result.get(), "skipped")
        self.create.assert_not_called()

    def test_missing_analysis_is_ignored(self):
        result = generate_coaching_report.apply(args=(999999,), throw=False)
        self.assertEqual(result.get(), "missing")
        self.create.assert_not_called()

    def test_processing_status_is_set_before_call(self):
        seen = {}

        def capture(**kwargs):
            seen["status"] = VideoAnalysis.objects.get(
                pk=self.analysis.pk
            ).report_status
            return fake_response()

        self.create.side_effect = capture
        self._run()
        self.assertEqual(seen["status"], "processing")
        self.assertEqual(self.analysis.report_status, "done")
