import django.contrib.gis.db.models.fields
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Gym",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(db_comment="암장 상호", max_length=100)),
                ("description", models.TextField(blank=True, db_comment="소개글")),
                ("address", models.CharField(db_comment="도로명 주소", max_length=200)),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(
                        db_comment="위치 좌표 (WGS84). 거리·뷰포트 검색용",
                        geography=True,
                        srid=4326,
                    ),
                ),
                (
                    "phone",
                    models.CharField(blank=True, db_comment="전화번호", max_length=20),
                ),
                (
                    "website",
                    models.URLField(blank=True, db_comment="홈페이지/카카오맵 URL"),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_comment="생성 시각", db_index=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_comment="마지막 수정 시각"),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_comment="soft delete 여부 (True면 삭제된 행)",
                        db_index=True,
                        default=False,
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, db_comment="soft delete 시각", null=True
                    ),
                ),
            ],
            options={
                "db_table_comment": "클라이밍 암장 — Kakao Local API로 수집. 위치는 PostGIS Point",
                "indexes": [
                    models.Index(fields=["name"], name="gyms_gym_name_ee4a7a_idx")
                ],
            },
        ),
        migrations.CreateModel(
            name="GymFacility",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        db_comment="편의시설 이름 (예: 샤워실, 주차장)", max_length=50
                    ),
                ),
                (
                    "gym",
                    models.ForeignKey(
                        db_comment="암장 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="facilities",
                        to="gyms.gym",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_comment="생성 시각", db_index=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_comment="마지막 수정 시각"),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_comment="soft delete 여부 (True면 삭제된 행)",
                        db_index=True,
                        default=False,
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, db_comment="soft delete 시각", null=True
                    ),
                ),
            ],
            options={"db_table_comment": "암장 편의시설 — 샤워실/주차장 등 태그"},
        ),
        migrations.CreateModel(
            name="GymImage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("image", models.URLField(db_comment="이미지 URL (S3)")),
                (
                    "order",
                    models.PositiveSmallIntegerField(db_comment="노출 순서", default=0),
                ),
                (
                    "gym",
                    models.ForeignKey(
                        db_comment="암장 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="gyms.gym",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_comment="생성 시각", db_index=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_comment="마지막 수정 시각"),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_comment="soft delete 여부 (True면 삭제된 행)",
                        db_index=True,
                        default=False,
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, db_comment="soft delete 시각", null=True
                    ),
                ),
            ],
            options={
                "db_table_comment": "암장 사진 — 상세 페이지 갤러리. order 순으로 노출",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="GymPrice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        db_comment="이용권 이름 (예: 1일권, 월회원권)", max_length=50
                    ),
                ),
                ("price", models.PositiveIntegerField(db_comment="금액 (원)")),
                (
                    "note",
                    models.CharField(blank=True, db_comment="비고", max_length=100),
                ),
                (
                    "gym",
                    models.ForeignKey(
                        db_comment="암장 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prices",
                        to="gyms.gym",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_comment="생성 시각", db_index=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_comment="마지막 수정 시각"),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_comment="soft delete 여부 (True면 삭제된 행)",
                        db_index=True,
                        default=False,
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, db_comment="soft delete 시각", null=True
                    ),
                ),
            ],
            options={"db_table_comment": "암장 가격표 — 암장당 여러 이용권"},
        ),
        migrations.CreateModel(
            name="GymDifficulty",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        db_comment="난이도 이름 (예: 초록, V3)", max_length=30
                    ),
                ),
                (
                    "color",
                    models.CharField(
                        db_comment="hex 색상 — 프론트는 이 DB 값을 그대로 렌더링",
                        max_length=7,
                    ),
                ),
                (
                    "order",
                    models.PositiveSmallIntegerField(
                        db_comment="난이도 순서 (쉬움 0 → 어려움)", default=0
                    ),
                ),
                (
                    "gym",
                    models.ForeignKey(
                        db_comment="암장 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="difficulties",
                        to="gyms.gym",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_comment="생성 시각", db_index=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_comment="마지막 수정 시각"),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_comment="soft delete 여부 (True면 삭제된 행)",
                        db_index=True,
                        default=False,
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, db_comment="soft delete 시각", null=True
                    ),
                ),
            ],
            options={
                "db_table_comment": "암장별 색 난이도 체계 — 등반 기록은 자유 문자열 대신 이 FK를 참조",
                "ordering": ["order", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_deleted", False)),
                        fields=("gym", "name"),
                        name="uniq_gym_difficulty_name",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="GymReview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        db_comment="별점 1~5",
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                ("content", models.TextField(db_comment="리뷰 본문")),
                (
                    "gym",
                    models.ForeignKey(
                        db_comment="암장 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="gyms.gym",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_comment="작성자 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gym_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_comment="생성 시각", db_index=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_comment="마지막 수정 시각"),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_comment="soft delete 여부 (True면 삭제된 행)",
                        db_index=True,
                        default=False,
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, db_comment="soft delete 시각", null=True
                    ),
                ),
            ],
            options={
                "db_table_comment": "암장 리뷰 — 별점 1~5 + 본문",
                "indexes": [
                    models.Index(
                        fields=["gym", "-created_at"],
                        name="gyms_gymrev_gym_id_ee37d2_idx",
                    )
                ],
            },
        ),
    ]
