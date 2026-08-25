import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("gyms", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
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
                    "user",
                    models.OneToOneField(
                        db_comment="회원 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("bio", models.TextField(blank=True, db_comment="자기소개")),
                (
                    "image",
                    models.URLField(blank=True, db_comment="프로필 이미지 URL (S3)"),
                ),
                (
                    "home_gym",
                    models.ForeignKey(
                        blank=True,
                        db_comment="주로 다니는 암장 FK",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
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
                "db_table_comment": "회원 프로필 — 소개글/이미지/홈짐. User와 1:1",
            },
        ),
    ]
