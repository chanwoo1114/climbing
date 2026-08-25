"""영상 분석은 반드시 Celery 태스크로. 상태는 VideoAnalysis.status로 관리."""

from celery import shared_task


@shared_task(bind=True, max_retries=1)
def analyze_video(self, analysis_id: int):
    """S3 다운로드 → OpenCV 샘플링 → MediaPipe Pose → 지표 계산 → JSONB 저장.

    TODO(M7): docs/개발정의.md 4장 파이프라인 구현.
    """
    raise NotImplementedError
