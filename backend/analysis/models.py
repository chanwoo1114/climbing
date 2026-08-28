from django.db import models

from common.models import BaseModel


class VideoAnalysis(BaseModel):
    """등반 영상 AI 자세 분석 — 기록당 1건. 처리는 Celery(analysis.tasks.analyze_video).

    상태 흐름: pending → processing → done | failed.
    failed 는 다시 POST 하면 pending 으로 돌려 재요청할 수 있다.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        PROCESSING = "processing", "분석 중"
        DONE = "done", "완료"
        FAILED = "failed", "실패"

    class ReportStatus(models.TextChoices):
        """AI 코칭 리포트 상태 — 자세 분석(status=done) 뒤에 별도로 요청한다.

        none → pending → processing → done | failed. done/failed 에서 다시 요청하면
        pending 으로 돌아가 재생성한다.
        """

        NONE = "none", "미생성"
        PENDING = "pending", "대기"
        PROCESSING = "processing", "생성 중"
        DONE = "done", "완료"
        FAILED = "failed", "실패"

    climb_log = models.OneToOneField(
        "climbs.ClimbLog",
        on_delete=models.CASCADE,
        related_name="analysis",
        db_comment="분석 대상 등반 기록 FK (기록당 1건)",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        db_comment="pending(대기) / processing(분석 중) / done(완료) / failed(실패)",
    )
    error_message = models.TextField(
        blank=True, db_comment="실패 사유 (사용자에게 그대로 보여줄 수 있는 짧은 문장)"
    )
    keypoints = models.JSONField(
        default=dict,
        blank=True,
        db_comment=(
            "샘플링 프레임별 MediaPipe Pose 33 랜드마크. "
            '{"fps": n, "frames": [{"t": 초, "lm": [[x, y, z, vis] × 33] | null}]}'
        ),
    )
    metrics = models.JSONField(
        default=dict,
        blank=True,
        db_comment="지표 요약 — 무게중심 궤적/이동 거리/상승량, 관절 각도 통계, 무브 비율, 길이",
    )
    processed_at = models.DateTimeField(
        null=True, blank=True, db_comment="분석 완료(done) 시각"
    )
    retry_count = models.PositiveSmallIntegerField(
        default=0, db_comment="워커 재시도 횟수 (네트워크성 실패만 1회 재시도)"
    )
    task_id = models.CharField(
        max_length=64, blank=True, db_comment="마지막으로 큐에 넣은 Celery task id"
    )

    # --- AI 코칭 리포트 (analysis.coaching, Celery: generate_coaching_report) ---
    report_status = models.CharField(
        max_length=12,
        choices=ReportStatus.choices,
        default=ReportStatus.NONE,
        db_index=True,
        db_comment="코칭 리포트 상태 — none(미생성)/pending/processing/done/failed",
    )
    report = models.TextField(
        blank=True, db_comment="LLM 이 생성한 코칭 리포트 본문 (한국어 markdown)"
    )
    report_error = models.TextField(
        blank=True, db_comment="리포트 생성 실패 사유 (사용자에게 보여줄 수 있는 문장)"
    )
    report_model = models.CharField(
        max_length=64, blank=True, db_comment="리포트를 생성한 LLM 모델 id (응답 기준)"
    )
    report_input_tokens = models.PositiveIntegerField(
        default=0, db_comment="리포트 생성에 쓴 입력 토큰 수"
    )
    report_output_tokens = models.PositiveIntegerField(
        default=0, db_comment="리포트 생성에 쓴 출력 토큰 수"
    )
    report_generated_at = models.DateTimeField(
        null=True, blank=True, db_comment="리포트 생성 완료(done) 시각"
    )
    report_task_id = models.CharField(
        max_length=64,
        blank=True,
        db_comment="마지막으로 큐에 넣은 리포트 생성 Celery task id",
    )

    class Meta:
        db_table_comment = "등반 영상 AI 자세 분석 — 기록당 1건, 상태/랜드마크/지표"

    def __str__(self):
        return f"analysis {self.id} of log {self.climb_log_id} [{self.status}]"

    @property
    def is_finished(self) -> bool:
        return self.status in (self.Status.DONE, self.Status.FAILED)
