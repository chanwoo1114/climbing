from django.contrib import admin

from gyms.models import (
    Gym,
    GymDifficulty,
    GymImage,
    GymManager,
    GymPrice,
    GymReview,
)


class GymDifficultyInline(admin.TabularInline):
    model = GymDifficulty
    extra = 0


class GymPriceInline(admin.TabularInline):
    model = GymPrice
    extra = 0


class GymImageInline(admin.TabularInline):
    model = GymImage
    extra = 0


@admin.register(Gym)
class GymAdmin(admin.ModelAdmin):
    """크롤러 수집 데이터 검수용 — 오분류(용품점 등) 삭제, 정보 보정."""

    list_display = ("name", "address", "phone", "created_at")
    search_fields = ("name", "address")
    inlines = [GymDifficultyInline, GymPriceInline, GymImageInline]


@admin.register(GymReview)
class GymReviewAdmin(admin.ModelAdmin):
    list_display = ("gym", "user", "rating", "created_at")
    search_fields = ("gym__name", "user__nickname")
    raw_id_fields = ("gym", "user")


@admin.register(GymManager)
class GymManagerAdmin(admin.ModelAdmin):
    """첫 관리자 지정은 여기서 — 이후 관리자 추가/해제는 API 로."""

    list_display = ("gym", "user", "note", "created_at")
    search_fields = ("gym__name", "user__nickname", "user__email")
    raw_id_fields = ("gym", "user", "assigned_by")
