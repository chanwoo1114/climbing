"""analysis 도메인 서비스 함수. 다중 모델 변경은 transaction.atomic.

요청(request_analysis)은 API 에서, 상태 전이(mark_*)는 Celery 태스크에서 부른다.
"""

import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from analysis.coaching import is_configured
from analysis.exceptions import (
    AnalysisNotDone,
    CoachingNotConfigured,
    ReportInProgress,
    VideoRequired,
)
from analysis.models import VideoAnalysis
from climbs.models import ClimbLog
from notifications.services import notify_analysis_status, notify_report_status

logger = logging.getLogger(__name__)


def visible_analyses(user):
    """요청자가 볼 수 있는 분석 — climbs 의 공개 규칙과 동일 (본인 기록 전부 + 남의 공개 기록)."""
    return (
        VideoAnalysis.objects.select_related("climb_log")
        .filter(climb_log__is_deleted=False)
        .filter(Q(climb_log__user=user) | Q(climb_log__is_shared=True))
        .order_by("-created_at")
    )


def owned_analyses(user):
    """요청자 본인 기록의 분석만 — 리포트 생성처럼 작성자 전용 액션에 쓴다 (남의 건 404)."""
    return (
        VideoAnalysis.objects.select_related("climb_log")
        .filter(climb_log__is_deleted=False, climb_log__user=user)
        .order_by("-created_at")
    )


@transaction.atomic
def request_analysis(log: ClimbLog, user) -> tuple[VideoAnalysis, bool]:
    """기록의 영상 분석을 요청한다. (analysis, 새로 큐에 넣었는지) 를 돌려준다.

    - 작성자만 (403), 영상이 없으면 video_required (400)
    - 기록당 1건: 이미 대기/진행/완료 상태면 그대로 돌려준다 (큐에 다시 넣지 않음)
    - failed 이거나 soft delete 된 건은 pending 으로 초기화해 다시 큐에 넣는다
    """
    if log.user_id != user.id:
        raise PermissionDenied("본인 기록의 영상만 분석할 수 있습니다.")
    if not log.video_url:
        raise VideoRequired()

    analysis = (
        VideoAnalysis.all_objects.select_for_update().filter(climb_log=log).first()
    )
    if analysis is None:
        analysis = VideoAnalysis.objects.create(climb_log=log)
    elif analysis.is_deleted or analysis.status == VideoAnalysis.Status.FAILED:
        _reset(analysis)
    else:
        return analysis, False

    enqueue_analysis(analysis)
    return analysis, True


def _reset(analysis: VideoAnalysis):
    analysis.is_deleted = False
    analysis.deleted_at = None
    analysis.status = VideoAnalysis.Status.PENDING
    analysis.error_message = ""
    analysis.keypoints = {}
    analysis.metrics = {}
    analysis.processed_at = None
    analysis.retry_count = 0
    analysis.task_id = ""
    # 지표가 바뀌므로 예전 리포트도 무효
    analysis.report_status = VideoAnalysis.ReportStatus.NONE
    analysis.report = ""
    analysis.report_error = ""
    analysis.report_model = ""
    analysis.report_input_tokens = 0
    analysis.report_output_tokens = 0
    analysis.report_generated_at = None
    analysis.report_task_id = ""
    analysis.save()


def enqueue_analysis(analysis: VideoAnalysis):
    """커밋 후 Celery 태스크에 넣는다 — 롤백된 행을 워커가 찾지 못하는 일을 막는다."""
    from analysis.tasks import analyze_video  # 순환 import 회피 (tasks → services)

    analysis_id = analysis.id

    def _send():
        result = analyze_video.delay(analysis_id)
        VideoAnalysis.all_objects.filter(pk=analysis_id).update(
            task_id=str(result.id or "")
        )

    transaction.on_commit(_send)


# --- 워커가 부르는 상태 전이 --------------------------------------------------


def mark_processing(analysis: VideoAnalysis):
    analysis.status = VideoAnalysis.Status.PROCESSING
    analysis.error_message = ""
    analysis.save(update_fields=["status", "error_message", "updated_at"])


def bump_retry(analysis: VideoAnalysis):
    analysis.retry_count += 1
    analysis.save(update_fields=["retry_count", "updated_at"])


def mark_done(analysis: VideoAnalysis, keypoints: dict, metrics: dict):
    analysis.status = VideoAnalysis.Status.DONE
    analysis.keypoints = keypoints
    analysis.metrics = metrics
    analysis.error_message = ""
    analysis.processed_at = timezone.now()
    analysis.save(
        update_fields=[
            "status",
            "keypoints",
            "metrics",
            "error_message",
            "processed_at",
            "updated_at",
        ]
    )
    notify_analysis_status(analysis)


def mark_failed(analysis: VideoAnalysis, message: str):
    analysis.status = VideoAnalysis.Status.FAILED
    analysis.error_message = message
    analysis.save(update_fields=["status", "error_message", "updated_at"])
    notify_analysis_status(analysis)


# --- AI 코칭 리포트 -----------------------------------------------------------

REPORT_ACTIVE = (
    VideoAnalysis.ReportStatus.PENDING,
    VideoAnalysis.ReportStatus.PROCESSING,
)


@transaction.atomic
def request_coaching_report(analysis: VideoAnalysis) -> VideoAnalysis:
    """코칭 리포트 생성을 요청한다 (pending 으로 두고 커밋 후 큐잉).

    - API 키가 없으면 coaching_not_configured (503)
    - 자세 분석이 done 이 아니면 analysis_not_done (409)
    - 이미 pending/processing 이면 report_in_progress (409)
    - none / done(재생성) / failed 에서 허용
    """
    if not is_configured():
        raise CoachingNotConfigured()

    analysis = VideoAnalysis.objects.select_for_update().get(pk=analysis.pk)
    if analysis.status != VideoAnalysis.Status.DONE:
        raise AnalysisNotDone()
    if analysis.report_status in REPORT_ACTIVE:
        raise ReportInProgress()

    analysis.report_status = VideoAnalysis.ReportStatus.PENDING
    analysis.report_error = ""
    analysis.report_task_id = ""
    analysis.save(
        update_fields=["report_status", "report_error", "report_task_id", "updated_at"]
    )
    enqueue_coaching_report(analysis)
    return analysis


def enqueue_coaching_report(analysis: VideoAnalysis):
    """커밋 후 Celery 태스크에 넣는다 (enqueue_analysis 와 같은 이유)."""
    from analysis.tasks import generate_coaching_report  # 순환 import 회피

    analysis_id = analysis.id

    def _send():
        result = generate_coaching_report.delay(analysis_id)
        VideoAnalysis.all_objects.filter(pk=analysis_id).update(
            report_task_id=str(result.id or "")
        )

    transaction.on_commit(_send)


def mark_report_processing(analysis: VideoAnalysis):
    analysis.report_status = VideoAnalysis.ReportStatus.PROCESSING
    analysis.report_error = ""
    analysis.save(update_fields=["report_status", "report_error", "updated_at"])


def mark_report_failed(analysis: VideoAnalysis, message: str):
    analysis.report_status = VideoAnalysis.ReportStatus.FAILED
    analysis.report_error = message
    analysis.save(update_fields=["report_status", "report_error", "updated_at"])
    notify_report_status(analysis)
