from django.contrib import admin

from analysis.models import VideoAnalysis


@admin.register(VideoAnalysis)
class VideoAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "climb_log",
        "status",
        "retry_count",
        "processed_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("climb_log__user__nickname", "error_message", "task_id")
    raw_id_fields = ("climb_log",)
    readonly_fields = ("keypoints", "metrics", "task_id", "processed_at")
