"""자세 분석 / 코칭 리포트 완료·실패 알림 — notifications.services 훅 연동.

기록 작성자에게 analysis_done / analysis_failed / report_done / report_failed 가 생기고,
이동 대상은 기록 상세(climb_log) 다.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from accounts.tests.helpers import create_verified_user
from analysis.coaching import generate_report
from analysis.models import VideoAnalysis
from analysis.services import mark_done, mark_failed, mark_report_failed
from analysis.tests.helpers import VIDEO_URL, create_analysis, make_keypoints
from climbs.tests.helpers import create_gym, create_log
from notifications.models import Notification
from notifications.tests.helpers import IN_MEMORY_CHANNELS


def _notifications(user):
    return list(Notification.objects.filter(recipient=user).order_by("id"))


@override_settings(**IN_MEMORY_CHANNELS)
class AnalysisNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_verified_user()
        cls.gym = create_gym()

    def setUp(self):
        self.log = create_log(self.user, self.gym, video_url=VIDEO_URL)
        self.analysis = create_analysis(self.log)

    def test_done_notifies_owner(self):
        mark_done(self.analysis, make_keypoints(), {"duration": 3.0})
        items = _notifications(self.user)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].type, "analysis_done")
        self.assertEqual(
            (items[0].target_type, items[0].target_id), ("climb_log", self.log.id)
        )
        self.assertIsNone(items[0].actor_id)

    def test_failed_notifies_owner_with_reason(self):
        mark_failed(self.analysis, "영상을 내려받지 못했습니다")
        items = _notifications(self.user)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].type, "analysis_failed")
        self.assertIn("영상을 내려받지 못했습니다", items[0].message)

    def test_report_failed_notifies_owner(self):
        mark_report_failed(self.analysis, "잠시 후 다시 시도해 주세요")
        items = _notifications(self.user)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].type, "report_failed")
        self.assertIn("잠시 후 다시 시도해 주세요", items[0].message)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_report_done_notifies_owner(self):
        mark_done(self.analysis, make_keypoints(), {"duration": 3.0})
        Notification.objects.all().delete()
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="## 한눈에 보기\n좋아요")],
            stop_reason="end_turn",
            model="claude-opus-5",
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            stop_details=None,
        )
        with patch("analysis.coaching._client") as client:
            client.return_value.messages.create.return_value = response
            generate_report(self.analysis)

        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.report_status, VideoAnalysis.ReportStatus.DONE)
        items = _notifications(self.user)
        self.assertEqual([n.type for n in items], ["report_done"])
        self.assertEqual(items[0].target_id, self.log.id)
