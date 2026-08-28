"""암장 관리자 기능 서비스 — 뷰는 얇게, 권한 판단·다중 모델 변경은 여기서."""

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import User
from gyms.exceptions import LastManager
from gyms.models import (
    Gym,
    GymDifficulty,
    GymFacility,
    GymImage,
    GymManager,
    GymPrice,
)

GYM_EDITABLE_FIELDS = ("name", "description", "address", "phone", "website")


# ---------- 관리자 판정 ----------


def is_gym_manager(gym: Gym, user) -> bool:
    """운영자(is_staff)는 항상 True. 그 외엔 살아있는 GymManager 행이 있어야 한다."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return GymManager.objects.filter(gym=gym, user=user).exists()


def managed_gyms(user):
    """내가 관리하는 암장 — 명시적 GymManager 행 기준 (staff 라도 전체를 주지 않는다)."""
    return (
        Gym.objects.filter(managers__user=user, managers__is_deleted=False)
        .prefetch_related("images")
        .order_by("name", "id")
        .distinct()
    )


def gym_managers(gym: Gym):
    return (
        GymManager.objects.filter(gym=gym)
        .select_related("user__profile")
        .order_by("created_at", "id")
    )


@transaction.atomic
def add_manager(
    gym: Gym, user_id: int, assigned_by, note: str = ""
) -> tuple[GymManager, bool]:
    """관리자 추가. (row, created) — 이미 관리자면 created=False (멱등).

    soft delete 된 행이 있으면 새로 만들지 않고 복구한다 (조건부 unique 와 이력 유지).
    """
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise NotFound("존재하지 않는 사용자입니다.")

    row = GymManager.all_objects.filter(gym=gym, user=user).order_by("-id").first()
    if row is not None and not row.is_deleted:
        return row, False
    if row is not None:
        row.assigned_by = assigned_by
        row.note = note
        row.save(update_fields=["assigned_by", "note", "updated_at"])
        row.restore()
        return row, True
    row = GymManager.objects.create(
        gym=gym, user=user, assigned_by=assigned_by, note=note
    )
    return row, True


@transaction.atomic
def remove_manager(gym: Gym, user_id: int, *, force: bool = False) -> None:
    """관리자 해제 (soft delete).

    마지막 남은 관리자는 해제할 수 없다 → 409 last_manager. force=True(운영자)면 허용.
    암장 행을 잠가 동시 해제로 관리자가 0명이 되는 경합을 막는다.
    """
    Gym.objects.select_for_update().get(pk=gym.pk)
    row = GymManager.objects.filter(gym=gym, user_id=user_id).first()
    if row is None:
        raise NotFound("해당 암장의 관리자가 아닙니다.")
    if not force and not GymManager.objects.filter(gym=gym).exclude(pk=row.pk).exists():
        raise LastManager()
    row.delete()


# ---------- 암장 정보 ----------


def update_gym(gym: Gym, **fields) -> Gym:
    changed = []
    for name, value in fields.items():
        if name not in GYM_EDITABLE_FIELDS:
            continue  # location 등은 API 로 바꾸지 않는다
        setattr(gym, name, value)
        changed.append(name)
    if changed:
        gym.save(update_fields=[*changed, "updated_at"])
    return gym


# ---------- 난이도 ----------


def _ensure_unique_difficulty_name(gym: Gym, name: str, exclude_pk=None) -> None:
    queryset = GymDifficulty.objects.filter(gym=gym, name=name)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    if queryset.exists():
        raise ValidationError({"name": ["이미 있는 난이도 이름입니다."]})


def create_difficulty(gym: Gym, **fields) -> GymDifficulty:
    _ensure_unique_difficulty_name(gym, fields["name"])
    return GymDifficulty.objects.create(gym=gym, **fields)


def update_difficulty(difficulty: GymDifficulty, **fields) -> GymDifficulty:
    if "name" in fields:
        _ensure_unique_difficulty_name(
            difficulty.gym, fields["name"], exclude_pk=difficulty.pk
        )
    for name, value in fields.items():
        setattr(difficulty, name, value)
    difficulty.save()
    return difficulty


def delete_difficulty(difficulty: GymDifficulty) -> None:
    """soft delete. 이 난이도를 가리키는 등반 기록은 FK 를 그대로 유지한다
    (SET_NULL 은 hard delete 때만 동작 — 기록 카드는 all_objects 기준으로 계속 렌더링)."""
    difficulty.delete()


# ---------- 사진 ----------


def add_image(gym: Gym, image: str, order: int | None = None) -> GymImage:
    if order is None:
        last = GymImage.objects.filter(gym=gym).order_by("-order").first()
        order = last.order + 1 if last else 0
    return GymImage.objects.create(gym=gym, image=image, order=order)


@transaction.atomic
def reorder_images(gym: Gym, ids: list[int]) -> list[GymImage]:
    """ids 순서대로 order 를 0..n-1 로 매긴다. 목록에 없는 사진은 그 뒤로 밀린다.

    중복 id 나 이 암장 사진이 아닌 id 가 섞이면 400.
    """
    if len(ids) != len(set(ids)):
        raise ValidationError({"ids": ["중복된 사진 id 가 있습니다."]})
    images = {img.id: img for img in GymImage.objects.filter(gym=gym)}
    unknown = [i for i in ids if i not in images]
    if unknown:
        raise ValidationError({"ids": ["이 암장의 사진이 아닙니다: " + str(unknown)]})

    ordered = [images[i] for i in ids]
    rest = sorted(
        (img for img in images.values() if img.id not in set(ids)),
        key=lambda img: (img.order, img.id),
    )
    for position, img in enumerate([*ordered, *rest]):
        if img.order != position:
            img.order = position
            img.save(update_fields=["order", "updated_at"])
    return [*ordered, *rest]


# ---------- 가격표 / 편의시설 (전체 교체) ----------


@transaction.atomic
def replace_prices(gym: Gym, items: list[dict]) -> list[GymPrice]:
    """기존 행은 soft delete 하고 새로 만든다 (단순하고 이력이 남는다). 빈 목록이면 전부 삭제."""
    GymPrice.objects.filter(gym=gym).delete()
    return [GymPrice.objects.create(gym=gym, **item) for item in items]


@transaction.atomic
def replace_facilities(gym: Gym, items: list[dict]) -> list[GymFacility]:
    GymFacility.objects.filter(gym=gym).delete()
    return [GymFacility.objects.create(gym=gym, **item) for item in items]
