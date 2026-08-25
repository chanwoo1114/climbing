from django.db import models
from django.db.models.base import ModelBase
from django.utils import timezone

from common.managers import AllObjectsManager, SoftDeleteManager

# BaseModel이 물려주는 감사 컬럼. 테이블에서 항상 맨 뒤에 모아 둔다.
AUDIT_FIELDS = ("created_at", "updated_at", "is_deleted", "deleted_at")


class AuditFieldsLastMeta(ModelBase):
    """감사 컬럼을 테이블 맨 뒤로 보내는 메타클래스.

    Django는 추상 부모의 필드를 자식 필드보다 먼저 배치하기 때문에, 그대로 두면
    id 다음에 created_at/updated_at/... 이 오고 정작 도메인 컬럼이 뒤로 밀린다.
    컬럼 순서를 재배치해 `id → 도메인 컬럼 → 감사 컬럼` 으로 읽히게 한다.
    (마이그레이션의 CREATE TABLE 컬럼 순서에 그대로 반영된다.)
    """

    def __new__(mcs, name, bases, attrs, **kwargs):
        cls = super().__new__(mcs, name, bases, attrs, **kwargs)
        opts = cls._meta
        if opts.abstract:
            return cls

        audit = [f for f in opts.local_fields if f.name in AUDIT_FIELDS]
        if not audit:
            return cls

        rest = [f for f in opts.local_fields if f.name not in AUDIT_FIELDS]
        opts.local_fields = rest + audit
        opts._expire_cache()
        return cls


class BaseModel(models.Model, metaclass=AuditFieldsLastMeta):
    """모든 모델의 공용 베이스. is_active 필드를 새로 만들지 말 것."""

    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, db_comment="생성 시각"
    )
    updated_at = models.DateTimeField(auto_now=True, db_comment="마지막 수정 시각")
    is_deleted = models.BooleanField(
        default=False, db_index=True, db_comment="soft delete 여부 (True면 삭제된 행)"
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True, db_comment="soft delete 시각"
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
