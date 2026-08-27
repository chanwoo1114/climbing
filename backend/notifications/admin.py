from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "actor", "type", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("recipient__nickname", "actor__nickname", "message")
    raw_id_fields = ("recipient", "actor")
