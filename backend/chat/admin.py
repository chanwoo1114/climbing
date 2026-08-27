from django.contrib import admin

from chat.models import ChatRoom, ChatRoomMember, Message


class ChatRoomMemberInline(admin.TabularInline):
    model = ChatRoomMember
    extra = 0
    raw_id_fields = ("user",)


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_group", "direct_key", "created_by", "created_at")
    list_filter = ("is_group",)
    search_fields = ("name", "direct_key")
    raw_id_fields = ("created_by",)
    inlines = (ChatRoomMemberInline,)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "sender", "type", "created_at")
    list_filter = ("type",)
    search_fields = ("content", "sender__nickname")
    raw_id_fields = ("room", "sender")
