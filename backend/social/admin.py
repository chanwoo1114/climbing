from django.contrib import admin

from social.models import Follow


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    search_fields = ("follower__nickname", "following__nickname")
    raw_id_fields = ("follower", "following")
