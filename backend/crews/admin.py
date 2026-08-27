from django.contrib import admin

from crews.models import Crew, CrewMember


class CrewMemberInline(admin.TabularInline):
    model = CrewMember
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "home_gym",
        "join_type",
        "max_members",
        "is_feed_public",
        "created_at",
    )
    list_filter = ("join_type", "is_feed_public")
    search_fields = ("name", "owner__nickname")
    raw_id_fields = ("owner", "home_gym", "chat_room")
    inlines = [CrewMemberInline]


@admin.register(CrewMember)
class CrewMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "crew", "user", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("crew__name", "user__nickname")
    raw_id_fields = ("crew", "user")
