from rest_framework import serializers

from accounts.models import User
from chat.models import ChatRoomMember, Message

MESSAGE_MAX_LENGTH = 2000


class ChatUserSerializer(serializers.ModelSerializer):
    """메시지 보낸 사람 / 참여자 요약 (select_related("user__profile") 전제)."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nickname", "image")
        read_only_fields = fields

    def get_image(self, obj) -> str | None:
        try:
            return obj.profile.image or None
        except User.profile.RelatedObjectDoesNotExist:
            return None


class MessageSerializer(serializers.ModelSerializer):
    """읽기 전용. REST 응답과 WebSocket 브로드캐스트 페이로드가 같은 모양을 쓴다."""

    sender = ChatUserSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Message
        fields = ("id", "room_id", "sender", "type", "content", "created_at")
        read_only_fields = fields


class MessageCreateSerializer(serializers.Serializer):
    """REST POST / WebSocket "message" 공용 입력 검증."""

    content = serializers.CharField(
        max_length=MESSAGE_MAX_LENGTH,
        trim_whitespace=True,
        error_messages={
            "blank": "메시지 내용을 입력해 주세요.",
            "required": "메시지 내용을 입력해 주세요.",
            "max_length": f"메시지는 {MESSAGE_MAX_LENGTH}자 이하여야 합니다.",
        },
    )


class ReadSerializer(serializers.Serializer):
    message_id = serializers.IntegerField(min_value=1)


class DirectRoomRequestSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        error_messages={"does_not_exist": "존재하지 않는 회원입니다."},
    )


class LastMessageSerializer(serializers.Serializer):
    """목록용 마지막 메시지 — services.my_memberships 의 주석값에서 조립한다."""

    id = serializers.IntegerField()
    content = serializers.CharField()
    type = serializers.CharField()
    sender = serializers.DictField(allow_null=True)
    created_at = serializers.DateTimeField()


class ChatRoomListSerializer(serializers.ModelSerializer):
    """내 채팅방 목록/상세 공용. 인스턴스는 ChatRoomMember(annotated) 다.

    한 쿼리로 끝내기 위해 방·마지막 메시지·상대 정보를 전부 Subquery 주석으로 받는다
    (services.my_memberships 참고).
    """

    id = serializers.IntegerField(source="room_id", read_only=True)
    is_group = serializers.BooleanField(source="room.is_group", read_only=True)
    name = serializers.CharField(source="room.name", read_only=True)
    created_at = serializers.DateTimeField(source="room.created_at", read_only=True)
    peer = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True)
    last_read_message_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = ChatRoomMember
        fields = (
            "id",
            "is_group",
            "name",
            "peer",
            "member_count",
            "last_message",
            "unread_count",
            "last_read_message_id",
            "created_at",
        )
        read_only_fields = fields

    def get_peer(self, obj) -> dict | None:
        """1:1 방의 상대 회원. 그룹 방은 null."""
        if obj.room.is_group or obj.peer_id is None:
            return None
        return {
            "id": obj.peer_id,
            "nickname": obj.peer_nickname,
            "image": obj.peer_image or None,
        }

    def get_last_message(self, obj) -> dict | None:
        if obj.last_message_id is None:
            return None
        sender = None
        if obj.last_message_sender_id is not None:
            sender = {
                "id": obj.last_message_sender_id,
                "nickname": obj.last_message_sender_nickname,
            }
        return LastMessageSerializer(
            {
                "id": obj.last_message_id,
                "content": obj.last_message_content,
                "type": obj.last_message_type,
                "sender": sender,
                "created_at": obj.last_message_created_at,
            }
        ).data


class ChatRoomMemberSerializer(serializers.ModelSerializer):
    user = ChatUserSerializer(read_only=True)

    class Meta:
        model = ChatRoomMember
        fields = ("user", "joined_at", "last_read_message_id")
        read_only_fields = fields


class ChatRoomDetailSerializer(ChatRoomListSerializer):
    """상세 = 목록 항목 + 참여자 목록. 뷰가 context["members"] 로 넘긴다."""

    members = serializers.SerializerMethodField()

    class Meta(ChatRoomListSerializer.Meta):
        fields = ChatRoomListSerializer.Meta.fields + ("members",)
        read_only_fields = fields

    def get_members(self, obj) -> list:
        return ChatRoomMemberSerializer(self.context.get("members", []), many=True).data
