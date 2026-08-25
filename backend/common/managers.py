from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    """soft delete 통일 — 삭제는 is_deleted=True + deleted_at 기록."""

    def delete(self):
        from django.utils import timezone

        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """기본 매니저(objects) — is_deleted=False만 반환."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """all_objects — 삭제분 포함 전체 조회."""
