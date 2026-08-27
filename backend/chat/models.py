from django.db import models
from django.utils import timezone

from common.models import BaseModel


class ChatRoom(BaseModel):
    """채팅방. 1:1(DM)과 그룹(모집·크루 단톡방) 공용.

    1:1 방은 direct_key("{작은 user_id}:{큰 user_id}")가 DB UNIQUE 라 같은 두 사람의 방이
    두 개 생길 수 없다 (docs/개발정의.md 5장 6번). 그룹 방은 direct_key=NULL.
    """

    is_group = models.BooleanField(
        default=False, db_comment="그룹 채팅 여부 (False 면 1:1 DM)"
    )
    name = models.CharField(
        max_length=100, blank=True, db_comment="방 이름 (1:1 은 빈 문자열)"
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_chat_rooms",
        db_comment="방을 만든 회원 FK (탈퇴 시 NULL)",
    )
    direct_key = models.CharField(
        max_length=41,
        unique=True,
        null=True,
        blank=True,
        db_comment="1:1 방 중복 방지 키 '{min_user_id}:{max_user_id}'. 그룹 방은 NULL",
    )

    class Meta:
        db_table_comment = "채팅방 — 1:1 은 direct_key 로 유일, 그룹은 이름 보유"

    def __str__(self):
        return self.name or f"direct {self.direct_key}"

    @staticmethod
    def make_direct_key(user_id_a: int, user_id_b: int) -> str:
        low, high = sorted((int(user_id_a), int(user_id_b)))
        return f"{low}:{high}"


class ChatRoomMember(BaseModel):
    """방 참여자. 나가기/강퇴는 soft delete (다시 들어오면 restore)."""

    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="members", db_comment="방 FK"
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="chat_memberships",
        db_comment="참여 회원 FK",
    )
    # FK 대신 정수 — 메시지 soft delete 와 무관하게 "여기까지 읽음" 위치만 기억하면 된다.
    last_read_message_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        db_comment="마지막으로 읽은 메시지 id (NULL 이면 하나도 안 읽음)",
    )
    joined_at = models.DateTimeField(
        default=timezone.now, db_comment="입장 시각 (재입장 시 갱신)"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["room", "user"],
                condition=models.Q(is_deleted=False),
                name="uniq_chat_room_member",
            )
        ]
        indexes = [models.Index(fields=["user", "room"])]
        db_table_comment = "채팅방 참여자 — (방, 회원) 유일, 읽음 위치 보관"

    def __str__(self):
        return f"member {self.user_id}@{self.room_id}"


class Message(BaseModel):
    class Type(models.TextChoices):
        TEXT = "text", "일반"
        SYSTEM = "system", "시스템"

    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="messages", db_comment="방 FK"
    )
    sender = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chat_messages",
        db_comment="보낸 회원 FK. NULL 이면 시스템 메시지",
    )
    type = models.CharField(
        max_length=10,
        choices=Type.choices,
        default=Type.TEXT,
        db_comment="text | system",
    )
    content = models.TextField(db_comment="본문 (최대 2000자)")

    class Meta:
        indexes = [models.Index(fields=["room", "-id"])]
        db_table_comment = "채팅 메시지 — 방별 id 역순 조회"

    def __str__(self):
        return f"message {self.id} in {self.room_id}"
