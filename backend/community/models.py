from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import BaseModel

RECRUIT_CAPACITY_MIN = 2
RECRUIT_CAPACITY_MAX = 50


class Post(BaseModel):
    """커뮤니티 게시글. category=recruit 면 Recruitment(OneToOne)가 반드시 붙는다."""

    class Category(models.TextChoices):
        FREE = "free", "자유"
        RECRUIT = "recruit", "모집"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="posts",
        db_comment="작성자 FK",
    )
    category = models.CharField(
        max_length=10,
        choices=Category.choices,
        default=Category.FREE,
        db_comment="게시글 종류 (free 자유글 / recruit 모집글)",
    )
    title = models.CharField(max_length=100, db_comment="제목 (최대 100자)")
    content = models.TextField(db_comment="본문 (최대 5000자)")
    gym = models.ForeignKey(
        "gyms.Gym",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posts",
        db_comment="관련 암장 FK (선택). 암장이 지워지면 NULL",
    )
    view_count = models.PositiveIntegerField(
        default=0, db_comment="조회수 (작성자 본인 조회는 제외, F() 증가)"
    )

    class Meta:
        indexes = [
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["gym", "-created_at"]),
        ]
        db_table_comment = (
            "커뮤니티 게시글 — 자유글/모집글. 모집글은 Recruitment 와 1:1"
        )

    def __str__(self):
        return f"[{self.category}] {self.title}"

    @property
    def is_recruit(self) -> bool:
        return self.category == self.Category.RECRUIT


class PostImage(BaseModel):
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="images", db_comment="게시글 FK"
    )
    image = models.URLField(db_comment="이미지 URL (S3, presigned URL 로 직접 업로드)")
    order = models.PositiveSmallIntegerField(default=0, db_comment="노출 순서")

    class Meta:
        ordering = ["order", "id"]
        db_table_comment = "게시글 첨부 이미지"

    def __str__(self):
        return f"image {self.order} of post {self.post_id}"


class PostComment(BaseModel):
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="comments", db_comment="게시글 FK"
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="post_comments",
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
        indexes = [models.Index(fields=["post", "created_at"])]
        db_table_comment = "게시글 댓글 — parent 로 1단계 대댓글"

    def __str__(self):
        return f"comment {self.id} on post {self.post_id}"


class Recruitment(BaseModel):
    """투어 모집 정보. 정원(capacity)은 작성자를 포함한 인원이다.

    마감 플로우(docs/개발정의.md 4장): 정원 도달 또는 작성자 수동 마감 → status=closed
    → services.on_recruitment_closed 훅 (채팅방 생성은 chat 앱이 연결).
    """

    class JoinType(models.TextChoices):
        INSTANT = "instant", "선착순"
        APPROVAL = "approval", "승인제"

    class Status(models.TextChoices):
        OPEN = "open", "모집중"
        CLOSED = "closed", "마감"
        CANCELED = "canceled", "취소"

    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name="recruitment",
        db_comment="모집글 FK (category=recruit 인 Post 와 1:1)",
    )
    # 모집 대상 암장 — 지워지면 모집의 의미가 사라지므로 삭제를 막는다.
    gym = models.ForeignKey(
        "gyms.Gym",
        on_delete=models.PROTECT,
        related_name="recruitments",
        db_comment="투어 대상 암장 FK",
    )
    meet_at = models.DateTimeField(db_comment="모임 일시 (작성 시점 기준 미래)")
    capacity = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(RECRUIT_CAPACITY_MIN),
            MaxValueValidator(RECRUIT_CAPACITY_MAX),
        ],
        db_comment="정원 (작성자 포함, 2~50명)",
    )
    join_type = models.CharField(
        max_length=10,
        choices=JoinType.choices,
        default=JoinType.INSTANT,
        db_comment="참여 방식 (instant 선착순 즉시 승인 / approval 작성자 승인제)",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
        db_comment="모집 상태 (open 모집중 / closed 마감 / canceled 취소)",
    )
    chat_room = models.ForeignKey(
        "chat.ChatRoom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recruitments",
        db_comment="마감 시 생성된 그룹 채팅방 FK. 마감 전에는 NULL",
    )
    crew = models.ForeignKey(
        "crews.Crew",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recruitments",
        db_comment="크루 주최 모집일 때 크루 FK. NULL 이면 개인 모집",
    )

    class Meta:
        indexes = [models.Index(fields=["gym", "status", "meet_at"])]
        db_table_comment = "투어 모집 — 대상 암장/일시/정원/참여 방식/상태"

    def __str__(self):
        return f"recruitment {self.id} ({self.status}) for post {self.post_id}"

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN


class Participation(BaseModel):
    """모집 참여. 취소는 status=canceled + soft delete → 재참여 시 새 행."""

    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        APPROVED = "approved", "승인"
        REJECTED = "rejected", "거절"
        CANCELED = "canceled", "취소"

    recruitment = models.ForeignKey(
        Recruitment,
        on_delete=models.CASCADE,
        related_name="participations",
        db_comment="모집 FK",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="participations",
        db_comment="참여자 FK",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_comment="참여 상태 (pending 대기 / approved 승인 / rejected 거절 / canceled 취소)",
    )

    class Meta:
        constraints = [
            # 취소는 soft delete 라 살아있는 행만 유일하면 된다 (재참여 시 새 행).
            models.UniqueConstraint(
                fields=["recruitment", "user"],
                condition=models.Q(is_deleted=False),
                name="uniq_participation",
            )
        ]
        indexes = [models.Index(fields=["recruitment", "status"])]
        db_table_comment = "모집 참여 — (모집, 회원) 유일, 취소분은 soft delete"

    def __str__(self):
        return f"participation {self.user_id}→{self.recruitment_id} ({self.status})"


# drf-spectacular ENUM_NAME_OVERRIDES 용 (settings 에서 문자열 경로로 참조)
RECRUITMENT_JOIN_TYPE_CHOICES = Recruitment.JoinType.choices
