from django.contrib.gis.db import models as gis_models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import BaseModel


class Gym(BaseModel):
    name = models.CharField(max_length=100, db_comment="암장 상호")
    description = models.TextField(blank=True, db_comment="소개글")
    address = models.CharField(max_length=200, db_comment="도로명 주소")
    # 위치는 PostGIS PointField 통일 (lat/lng Float 금지)
    location = gis_models.PointField(
        geography=True, srid=4326, db_comment="위치 좌표 (WGS84). 거리·뷰포트 검색용"
    )
    phone = models.CharField(max_length=20, blank=True, db_comment="전화번호")
    website = models.URLField(blank=True, db_comment="홈페이지/카카오맵 URL")

    class Meta:
        indexes = [models.Index(fields=["name"])]
        db_table_comment = (
            "클라이밍 암장 — Kakao Local API로 수집. 위치는 PostGIS Point"
        )

    def __str__(self):
        return self.name


class GymImage(BaseModel):
    gym = models.ForeignKey(
        Gym, on_delete=models.CASCADE, related_name="images", db_comment="암장 FK"
    )
    image = models.URLField(db_comment="이미지 URL (S3)")
    order = models.PositiveSmallIntegerField(default=0, db_comment="노출 순서")

    class Meta:
        ordering = ["order", "id"]
        db_table_comment = "암장 사진 — 상세 페이지 갤러리. order 순으로 노출"

    def __str__(self):
        return f"{self.gym.name} 이미지 {self.order}"


class GymPrice(BaseModel):
    gym = models.ForeignKey(
        Gym, on_delete=models.CASCADE, related_name="prices", db_comment="암장 FK"
    )
    name = models.CharField(
        max_length=50, db_comment="이용권 이름 (예: 1일권, 월회원권)"
    )
    price = models.PositiveIntegerField(db_comment="금액 (원)")
    note = models.CharField(max_length=100, blank=True, db_comment="비고")

    class Meta:
        db_table_comment = "암장 가격표 — 암장당 여러 이용권"

    def __str__(self):
        return f"{self.gym.name} {self.name}"


class GymFacility(BaseModel):
    gym = models.ForeignKey(
        Gym, on_delete=models.CASCADE, related_name="facilities", db_comment="암장 FK"
    )
    name = models.CharField(
        max_length=50, db_comment="편의시설 이름 (예: 샤워실, 주차장)"
    )

    class Meta:
        db_table_comment = "암장 편의시설 — 샤워실/주차장 등 태그"

    def __str__(self):
        return f"{self.gym.name} {self.name}"


class GymDifficulty(BaseModel):
    """암장별 색 난이도. 난이도는 자유 문자열 금지 → 이 모델 FK 참조."""

    gym = models.ForeignKey(
        Gym, on_delete=models.CASCADE, related_name="difficulties", db_comment="암장 FK"
    )
    name = models.CharField(max_length=30, db_comment="난이도 이름 (예: 초록, V3)")
    color = models.CharField(
        max_length=7, db_comment="hex 색상 — 프론트는 이 DB 값을 그대로 렌더링"
    )
    order = models.PositiveSmallIntegerField(
        default=0, db_comment="난이도 순서 (쉬움 0 → 어려움)"
    )

    class Meta:
        ordering = ["order", "id"]
        db_table_comment = (
            "암장별 색 난이도 체계 — 등반 기록은 자유 문자열 대신 이 FK를 참조"
        )
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "name"],
                condition=models.Q(is_deleted=False),
                name="uniq_gym_difficulty_name",
            )
        ]

    def __str__(self):
        return f"{self.gym.name} {self.name}"


class GymReview(BaseModel):
    gym = models.ForeignKey(
        Gym, on_delete=models.CASCADE, related_name="reviews", db_comment="암장 FK"
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="gym_reviews",
        db_comment="작성자 FK",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_comment="별점 1~5",
    )
    content = models.TextField(db_comment="리뷰 본문")

    class Meta:
        indexes = [models.Index(fields=["gym", "-created_at"])]
        db_table_comment = "암장 리뷰 — 별점 1~5 + 본문"

    def __str__(self):
        return f"{self.gym.name} 리뷰 ({self.rating})"
