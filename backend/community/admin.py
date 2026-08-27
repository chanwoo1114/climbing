from django.contrib import admin

from community.models import Participation, Post, PostComment, PostImage, Recruitment


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "category",
        "title",
        "user",
        "gym",
        "view_count",
        "created_at",
    )
    list_filter = ("category",)
    search_fields = ("title", "content", "user__nickname")
    raw_id_fields = ("user", "gym")
    inlines = [PostImageInline]


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "user", "parent", "created_at")
    search_fields = ("user__nickname", "content")
    raw_id_fields = ("post", "user", "parent")


class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Recruitment)
class RecruitmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "gym",
        "meet_at",
        "capacity",
        "join_type",
        "status",
        "chat_room_id",
    )
    list_filter = ("status", "join_type")
    search_fields = ("post__title", "gym__name")
    raw_id_fields = ("post", "gym")
    inlines = [ParticipationInline]


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ("id", "recruitment", "user", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("recruitment", "user")
