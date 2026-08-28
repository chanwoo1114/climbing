from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from common.models import BaseModel


class ClimbLog(BaseModel):
    """등반 기록. is_shared=True 인 기록만 피드(탐색/팔로잉)에 노출된다."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="climb_logs",
        db_comment="작성자 FK",
    )
    # 암장이 지워지면 기록의 맥락이 사라지므로 삭제를 막는다 (soft delete 는 무관).
    gym = models.ForeignKey(
        "gyms.Gym",
        on_delete=models.PROTECT,
        related_name="climb_logs",
        db_comment="등반한 암장 FK",
    )
    # 난이도는 자유 문자열 금지 → 같은 암장의 GymDifficulty 만 허용 (serializer 검증)
    difficulty = models.ForeignKey(
        "gyms.GymDifficulty",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="climb_logs",
        db_comment="난이도 FK (암장별 색 난이도). 암장이 난이도를 지우면 NULL",
    )
    is_success = models.BooleanField(default=False, db_comment="완등 여부")
    attempts = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)], db_comment="시도 횟수 (1 이상)"
    )
    memo = models.TextField(blank=True, db_comment="메모 (최대 1000자)")
    video_url = models.URLField(
        blank=True, db_comment="등반 영상 URL (S3, presigned URL 로 직접 업로드)"
    )
    climbed_at = models.DateField(
        default=timezone.localdate, db_comment="등반한 날짜 (미래 불가)"
    )
    is_shared = models.BooleanField(
        default=True, db_comment="피드 공개 여부. False 면 본인만 조회"
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["gym", "-created_at"]),
            models.Index(fields=["is_shared", "-created_at"]),
        ]
        db_table_comment = (
            "등반 기록 — 암장/난이도/성공 여부/메모/영상. 공개분은 피드에 노출"
        )

    def __str__(self):
        return f"{self.user_id}:{self.gym_id} ({self.climbed_at})"


class ClimbLogLike(BaseModel):
    climb_log = models.ForeignKey(
        ClimbLog, on_delete=models.CASCADE, related_name="likes", db_comment="기록 FK"
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="climb_log_likes",
        db_comment="좋아요 누른 회원 FK",
    )

    class Meta:
        constraints = [
            # 취소는 soft delete 라 살아있는 행만 유일하면 된다 (재좋아요 시 복구).
            models.UniqueConstraint(
                fields=["climb_log", "user"],
                condition=models.Q(is_deleted=False),
                name="uniq_climb_log_like",
            )
        ]
        db_table_comment = "등반 기록 좋아요 — (기록, 회원) 유일"

    def __str__(self):
        return f"like {self.user_id}→{self.climb_log_id}"


class ClimbLogComment(BaseModel):
    climb_log = models.ForeignKey(
        ClimbLog,
        on_delete=models.CASCADE,
        related_name="comments",
        db_comment="기록 FK",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="climb_log_comments",
        db_comment="작성자 FK",
    )
    content = models.TextField(db_comment="댓글 본문 (최대 500자)")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        db_comment="부모 댓글 FK — 1단계 대댓글만 허용 (대댓글의 대댓글 불가)",
    )

    class Meta:
        indexes = [models.Index(fields=["climb_log", "created_at"])]
        db_table_comment = "등반 기록 댓글 — parent 로 1단계 대댓글"

    def __str__(self):
        return f"comment {self.id} on {self.climb_log_id}"


BETA_DESCRIPTION_MAX_LENGTH = 1000
BETA_SECTOR_MAX_LENGTH = 50


class ClimbBeta(BaseModel):
    """암장 섹터별 베타(문제 풀이) 영상. 조회는 공개, 작성·수정·삭제는 올린 사람만.

    섹터는 세팅 때마다 바뀌므로 별도 테이블 없이 자유 문자열로 둔다.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="climb_betas",
        db_comment="올린 회원 FK",
    )
    gym = models.ForeignKey(
        "gyms.Gym",
        on_delete=models.CASCADE,
        related_name="betas",
        db_comment="암장 FK",
    )
    # 난이도는 자유 문자열 금지 → 같은 암장의 GymDifficulty 만 허용 (serializer 검증)
    difficulty = models.ForeignKey(
        "gyms.GymDifficulty",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="betas",
        db_comment="난이도 FK (암장별 색 난이도). 암장이 난이도를 지우면 NULL",
    )
    sector = models.CharField(
        max_length=BETA_SECTOR_MAX_LENGTH,
        blank=True,
        db_comment="섹터/벽 이름 (예: A섹터, 슬랩 벽) — 자유 문자열, 세팅마다 바뀜",
    )
    title = models.CharField(max_length=100, db_comment="베타 제목")
    description = models.TextField(blank=True, db_comment="설명 (최대 1000자)")
    video_url = models.URLField(
        db_comment="베타 영상 URL (S3, presigned URL 로 직접 업로드). 생성 후 변경 불가"
    )
    thumbnail_url = models.URLField(blank=True, db_comment="썸네일 이미지 URL (S3)")
    climb_log = models.ForeignKey(
        ClimbLog,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="betas",
        db_comment="연결된 본인 등반 기록 FK (선택, 같은 암장 기록만)",
    )
    view_count = models.PositiveIntegerField(
        default=0, db_comment="조회수 — 상세 조회 때마다 F() 로 원자적 증가"
    )

    class Meta:
        indexes = [
            models.Index(fields=["gym", "-created_at"]),
            models.Index(fields=["gym", "sector"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        db_table_comment = "암장 섹터별 베타 영상 — 섹터/난이도/제목/영상. 조회는 공개"

    def __str__(self):
        return f"beta {self.id}: {self.title} @ {self.gym_id}"
