"""영상 분석은 반드시 Celery 태스크로. 상태는 VideoAnalysis.status로 관리."""

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from analysis.models import VideoAnalysis
from analysis.pipeline import ERROR_MESSAGES, AnalysisError, run_pipeline
from analysis.services import bump_retry, mark_done, mark_failed, mark_processing

logger = logging.getLogger(__name__)

RETRY_COUNTDOWN_SECONDS = 30


@shared_task(bind=True, max_retries=1, soft_time_limit=600)
def analyze_video(self, analysis_id: int) -> str:
    """S3 다운로드 → OpenCV 샘플링 → MediaPipe Pose → 지표 계산 → JSONB 저장.

    - 성공: keypoints/metrics 저장, status=done, processed_at 기록
    - 실패: status=failed + 사용자에게 보여줄 error_message
    - 네트워크성 실패(AnalysisError.retryable)만 1회 재시도 (retry_count 증가)
    """
    analysis = (
        VideoAnalysis.objects.select_related("climb_log").filter(pk=analysis_id).first()
    )
    if analysis is None:
        logger.warning("analyze_video: analysis %s not found", analysis_id)
        return "missing"
    if analysis.status == VideoAnalysis.Status.DONE:
        # 중복 큐잉 방어 — 이미 끝난 분석을 다시 돌리지 않는다.
        return "done"

    mark_processing(analysis)
    try:
        keypoints, metrics = run_pipeline(analysis.climb_log.video_url)
    except AnalysisError as exc:
        if exc.retryable and self.request.retries < self.max_retries:
            bump_retry(analysis)
            logger.info(
                "analyze_video: retrying analysis %s (%s)", analysis_id, exc.code
            )
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN_SECONDS)
        logger.warning("analyze_video: analysis %s failed: %s", analysis_id, exc)
        mark_failed(analysis, exc.message)
        return "failed"
    except SoftTimeLimitExceeded:
        logger.warning("analyze_video: analysis %s timed out", analysis_id)
        mark_failed(analysis, ERROR_MESSAGES["timeout"])
        return "failed"
    except Exception:
        logger.exception("analyze_video: analysis %s crashed", analysis_id)
        mark_failed(analysis, ERROR_MESSAGES["unknown"])
        return "failed"

    mark_done(analysis, keypoints, metrics)
    return "done"
