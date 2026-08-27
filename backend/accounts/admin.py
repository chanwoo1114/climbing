from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import SocialAccount, User, UserProfile


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """이메일 로그인 커스텀 User 용 admin.

    기본 UserAdmin 은 username 기준이라 그대로 쓰면 깨진다.
    탈퇴 계정도 봐야 하므로 all_objects 를 쓴다.
    """

    ordering = ("-created_at",)
    list_display = ("email", "nickname", "is_staff", "is_deleted", "created_at")
    list_filter = ("is_staff", "is_deleted")
    search_fields = ("email", "nickname")
    readonly_fields = ("last_login", "created_at", "updated_at", "deleted_at")

    fieldsets = (
        (None, {"fields": ("email", "nickname", "password")}),
        ("권한", {"fields": ("is_staff", "is_superuser", "groups")}),
        ("상태", {"fields": ("is_deleted", "deleted_at", "last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "nickname", "password1", "password2")}),
    )

    def get_queryset(self, request):
        return User.all_objects.all()


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "home_gym", "created_at")
    search_fields = ("user__email", "user__nickname")
    raw_id_fields = ("user", "home_gym")


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "provider_uid", "connected_at", "is_deleted")
    list_filter = ("provider", "is_deleted")
    search_fields = ("user__email", "user__nickname", "provider_uid")
    raw_id_fields = ("user",)

    def get_queryset(self, request):
        return SocialAccount.all_objects.select_related("user")
