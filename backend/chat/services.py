"""chat 도메인 서비스 함수. 다중 모델 변경은 transaction.atomic.

다른 앱(community 모집 마감, crews 단톡방)이 호출하는 공개 함수:

    create_group_room(*, name, member_ids, created_by, system_message=None) -> ChatRoom
    add_members(room, user_ids) -> list[ChatRoomMember]
    remove_member(room, user, system_message=None) -> bool
    post_system_message(room, content) -> Message
    get_or_create_direct_room(user_a, user_b) -> tuple[ChatRoom, bool]

메시지를 만드는 함수(send_message / post_system_message)는 저장 직후 채널 레이어 그룹
``chat_{room_id}`` 로 브로드캐스트해서 REST 로 보낸 메시지도 WebSocket 접속자에게 닿는다.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers

from chat.models import ChatRoom, ChatRoomMember, Message

logger = logging.getLogger(__name__)


# --- 채널 레이어 브로드캐스트 ------------------------------------------------


def room_group_name(room_id: int) -> str:
    return f"chat_{room_id}"


def broadcast(room_id: int, event: dict) -> None:
    """방 그룹으로 이벤트 전송. event["type"] 은 컨슈머 핸들러 이름(chat.message 등).

    실패해도 메시지 저장은 이미 끝났으므로 예외를 삼키고 로그만 남긴다
    (Redis 장애가 채팅 저장까지 막지 않게).
    """
    try:
        async_to_sync(get_channel_layer().group_send)(room_group_name(room_id), event)
    except Exception:  # noqa: BLE001 — 브로드캐스트는 best-effort
        logger.exception(
            "chat broadcast failed: room=%s type=%s", room_id, event.get("type")
        )


def serialize_message(message: Message) -> dict:
    """REST 응답과 WS 페이로드가 같은 모양을 쓰도록 한 곳에서 직렬화."""
    from chat.serializers import MessageSerializer

    return MessageSerializer(message).data


def broadcast_message(message: Message) -> None:
    broadcast(
        message.room_id, {"type": "chat.message", "message": serialize_message(message)}
    )


# --- 조회 --------------------------------------------------------------------


def get_membership(room_id: int, user) -> ChatRoomMember | None:
    return (
        ChatRoomMember.objects.select_related("room")
        .filter(room_id=room_id, user=user, room__is_deleted=False)
        .first()
    )


def _count_subquery(queryset):
    """OuterRef 로 묶인 쿼리셋의 행 수 — 값 하나짜리 Subquery 로."""
    return Coalesce(
        Subquery(
            queryset.order_by().values("room").annotate(c=Count("*")).values("c")[:1]
        ),
        0,
    )


def my_memberships(user):
    """내 채팅방 목록 — 단 한 쿼리.

    ChatRoomMember(내 참여 행) 기준으로 방·마지막 메시지·읽지 않은 수·1:1 상대를
    전부 Subquery 주석으로 가져온다. 정렬 키 last_activity_at 은 마지막 메시지 시각,
    메시지가 없으면 방 생성 시각.
    """
    latest = Message.objects.filter(room=OuterRef("room_id")).order_by("-id")
    unread = Message.objects.filter(
        room=OuterRef("room_id"), id__gt=Coalesce(OuterRef("last_read_message_id"), 0)
    )
    peer = (
        ChatRoomMember.objects.filter(room=OuterRef("room_id"))
        .exclude(user=user)
        .order_by("id")
    )
    return (
        ChatRoomMember.objects.filter(user=user, room__is_deleted=False)
        .select_related("room")
        .annotate(
            member_count=_count_subquery(
                ChatRoomMember.objects.filter(room=OuterRef("room_id"))
            ),
            unread_count=_count_subquery(unread),
            last_message_id=Subquery(latest.values("id")[:1]),
            last_message_content=Subquery(latest.values("content")[:1]),
            last_message_type=Subquery(latest.values("type")[:1]),
            last_message_sender_id=Subquery(latest.values("sender_id")[:1]),
            last_message_sender_nickname=Subquery(
                latest.values("sender__nickname")[:1]
            ),
            last_message_created_at=Subquery(latest.values("created_at")[:1]),
            peer_id=Subquery(peer.values("user_id")[:1]),
            peer_nickname=Subquery(peer.values("user__nickname")[:1]),
            peer_image=Subquery(peer.values("user__profile__image")[:1]),
        )
        .annotate(
            last_activity_at=Coalesce(
                F("last_message_created_at"), F("room__created_at")
            )
        )
        .order_by("-last_activity_at", "-room_id")
    )


def room_members(room: ChatRoom):
    return (
        ChatRoomMember.objects.filter(room=room)
        .select_related("user__profile")
        .order_by("joined_at", "id")
    )


def room_messages(room: ChatRoom):
    return Message.objects.filter(room=room).select_related("sender__profile")


# --- 1:1 방 ------------------------------------------------------------------


@transaction.atomic
def get_or_create_direct_room(user_a, user_b) -> tuple[ChatRoom, bool]:
    """두 회원의 1:1 방을 찾거나 만든다. (room, created).

    direct_key UNIQUE 덕분에 동시 요청이 와도 방은 하나만 생긴다
    (get_or_create 가 IntegrityError 를 잡고 다시 조회). 예전에 삭제된 방이면 복구.
    """
    if user_a.id == user_b.id:
        raise serializers.ValidationError(
            {"user_id": "자기 자신과는 대화할 수 없습니다."}
        )

    key = ChatRoom.make_direct_key(user_a.id, user_b.id)
    room, created = ChatRoom.all_objects.get_or_create(
        direct_key=key, defaults={"is_group": False, "created_by": user_a}
    )
    if room.is_deleted:
        room.restore()
    _ensure_members(room, [user_a.id, user_b.id])
    return room, created


# --- 그룹 방 (community / crews 가 호출) ----------------------------------------


@transaction.atomic
def create_group_room(
    *, name: str, member_ids: list[int], created_by, system_message: str | None = None
) -> ChatRoom:
    """그룹 채팅방 생성 + 참여자 일괄 등록 + 시스템 메시지.

    created_by 는 member_ids 에 없어도 자동으로 참여자에 포함된다.
    system_message 가 None 이면 "{name} 채팅방이 생성되었습니다" 를 남긴다.
    """
    room = ChatRoom.objects.create(is_group=True, name=name, created_by=created_by)
    ids = list(member_ids)
    if created_by is not None:
        ids.append(created_by.id)
    _ensure_members(room, ids)
    post_system_message(room, system_message or f"{name} 채팅방이 생성되었습니다")
    return room


@transaction.atomic
def add_members(room: ChatRoom, user_ids: list[int]) -> list[ChatRoomMember]:
    """참여자 추가 (이미 있으면 무시, 나갔던 사람은 복구). 추가/복구된 행을 돌려준다."""
    return _ensure_members(room, user_ids)


@transaction.atomic
def remove_member(room: ChatRoom, user, system_message: str | None = None) -> bool:
    """참여자 제거 (soft delete). 없었으면 False.

    system_message 가 있으면 방에 남기고, 제거된 회원의 WebSocket 은 끊기도록
    chat.member_removed 이벤트를 보낸다.
    """
    member = ChatRoomMember.objects.filter(room=room, user=user).first()
    if member is None:
        return False
    member.delete()
    # 제거 이벤트를 먼저 보내야 나간 사람이 뒤따르는 시스템 메시지를 받지 않는다.
    broadcast(room.id, {"type": "chat.member_removed", "user_id": user.id})
    if system_message:
        post_system_message(room, system_message)
    return True


def _ensure_members(room: ChatRoom, user_ids) -> list[ChatRoomMember]:
    """중복 없이 참여자 행을 만든다. soft delete 된 행은 restore + joined_at 갱신."""
    changed = []
    for user_id in dict.fromkeys(user_ids):  # 순서 유지 중복 제거
        member, created = ChatRoomMember.all_objects.get_or_create(
            room=room, user_id=user_id
        )
        if not created and member.is_deleted:
            member.is_deleted = False
            member.deleted_at = None
            member.joined_at = timezone.now()
            member.save(
                update_fields=["is_deleted", "deleted_at", "joined_at", "updated_at"]
            )
            created = True
        if created:
            changed.append(member)
    return changed


# --- 메시지 ------------------------------------------------------------------


def send_message(room: ChatRoom, sender, content: str) -> Message:
    """일반 메시지 저장 + 보낸 사람 읽음 위치 갱신 + 브로드캐스트.

    멤버십 검증은 호출자(뷰/컨슈머) 책임.
    """
    with transaction.atomic():
        message = Message.objects.create(
            room=room, sender=sender, type=Message.Type.TEXT, content=content
        )
        _advance_last_read(room.id, sender.id, message.id)
    message = Message.objects.select_related("sender__profile").get(pk=message.pk)
    broadcast_message(message)
    return message


def post_system_message(room: ChatRoom, content: str) -> Message:
    """시스템 메시지 (sender=NULL) 저장 + 브로드캐스트."""
    message = Message.objects.create(
        room=room, sender=None, type=Message.Type.SYSTEM, content=content
    )
    broadcast_message(message)
    return message


def mark_read(member: ChatRoomMember, message_id: int) -> int | None:
    """읽음 위치를 message_id 로 올린다 (뒤로는 못 감). 갱신 후 값을 돌려준다."""
    if not Message.objects.filter(room_id=member.room_id, id=message_id).exists():
        raise serializers.ValidationError({"message_id": "이 방의 메시지가 아닙니다."})
    _advance_last_read(member.room_id, member.user_id, message_id)
    member.refresh_from_db(fields=["last_read_message_id"])
    broadcast(
        member.room_id,
        {
            "type": "chat.read",
            "user_id": member.user_id,
            "message_id": member.last_read_message_id,
        },
    )
    return member.last_read_message_id


def _advance_last_read(room_id: int, user_id: int, message_id: int) -> int:
    return (
        ChatRoomMember.objects.filter(room_id=room_id, user_id=user_id)
        .filter(
            Q(last_read_message_id__lt=message_id)
            | Q(last_read_message_id__isnull=True)
        )
        .update(last_read_message_id=message_id)
    )


@transaction.atomic
def leave_room(member: ChatRoomMember) -> None:
    """그룹 방 나가기. 1:1 방은 나갈 수 없다 (상대가 계속 볼 수 있어야 하므로)."""
    if not member.room.is_group:
        raise serializers.ValidationError({"detail": "1:1 대화방은 나갈 수 없습니다."})
    remove_member(member.room, member.user, f"{member.user.nickname}님이 나갔습니다")
