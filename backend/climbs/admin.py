from django.contrib import admin

from climbs.models import ClimbLog, ClimbLogComment


@admin.register(ClimbLog)
class ClimbLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "gym",
        "difficulty",
        "is_success",
        "attempts",
        "climbed_at",
        "is_shared",
        "created_at",
    )
    list_filter = ("is_success", "is_shared")
    search_fields = ("user__nickname", "gym__name", "memo")
    raw_id_fields = ("user", "gym", "difficulty")


@admin.register(ClimbLogComment)
class ClimbLogCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "climb_log", "user", "parent", "created_at")
    search_fields = ("user__nickname", "content")
    raw_id_fields = ("climb_log", "user", "parent")
