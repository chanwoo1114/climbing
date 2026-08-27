"""notifications 도메인 서비스 함수.

다른 앱의 서비스가 훅으로 부르는 공개 함수:

    notify(*, recipient, actor, type, target_type, target_id, message)
    notify_like(log, actor)                      climbs.like_log
    notify_comment(comment)                      climbs.create_comment (+ 답글이면 reply)
    notify_follow(follow)                        social.follow_user
    notify_recruitment_closed(recruitment, ids)  community.on_recruitment_closed
    notify_participation_status(participation)   community.set_participation_status
    notify_crew_member_status(member)            crews.set_member_status
    notify_crew_joined(member)                   crews.join_crew

알림 실패가 본 동작(좋아요·댓글·가입…)을 깨뜨리면 안 되므로 notify() 는 자체 savepoint
안에서 저장하고 어떤 예외도 밖으로 내보내지 않는다 (로그만). 본인이 본인에게 하는
행동(내 기록에 내가 댓글 등)은 알림을 만들지 않는다.
"""

import logging

from django.db import transaction
from django.utils import timezone

from notifications.models import MESSAGE_MAX_LENGTH, Notification
from notifications.tasks import deliver_notification

logger = logging.getLogger(__name__)

PREVIEW_LENGTH = 40

# 같은 (받는 사람, 행위자, 종류, 대상) 알림을 한 줄로 유지하는 종류 — 좋아요 토글 반복이
# 알림을 도배하지 않도록 기존 행을 갱신(created_at·is_read 리셋)한다.
DEDUPE_TYPES = frozenset({Notification.Type.LIKE})


def _pk(obj_or_id):
    return getattr(obj_or_id, "pk", obj_or_id)


def _truncate(text: str, length: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= length else text[: length - 1] + "…"


def _schedule_delivery(notification_id: int) -> None:
    try:
        deliver_notification.delay(notification_id)
    except Exception:  # noqa: BLE001 — 브로커 장애가 본 동작을 깨지 않게
        logger.exception("notification delivery enqueue failed: id=%s", notification_id)


def notify(
    *, recipient, actor, type: str, target_type: str, target_id: int, message: str
) -> Notification | None:
    """알림 저장 + 커밋 후 전달(Celery). 본인에게는 만들지 않는다 (None).

    recipient/actor 는 User 또는 id. 실패해도 예외를 내지 않고 None 을 돌려준다.
    """
    recipient_id = _pk(recipient)
    actor_id = _pk(actor)
    if recipient_id is None or recipient_id == actor_id:
        return None
    message = _truncate(message, MESSAGE_MAX_LENGTH)

    try:
        with transaction.atomic():
            if type in DEDUPE_TYPES:
                notification, _ = Notification.all_objects.update_or_create(
                    recipient_id=recipient_id,
                    actor_id=actor_id,
                    type=type,
                    target_type=target_type,
                    target_id=target_id,
                    defaults={
                        "message": message,
                        "is_read": False,
                        "read_at": None,
                        "is_deleted": False,
                        "deleted_at": None,
                        "created_at": timezone.now(),
                    },
                )
            else:
                notification = Notification.objects.create(
                    recipient_id=recipient_id,
                    actor_id=actor_id,
                    type=type,
                    target_type=target_type,
                    target_id=target_id,
                    message=message,
                )
            transaction.on_commit(lambda: _schedule_delivery(notification.id))
    except Exception:  # noqa: BLE001 — 알림 실패는 본 동작과 무관
        logger.exception(
            "notification create failed: recipient=%s type=%s target=%s:%s",
            recipient_id,
            type,
            target_type,
            target_id,
        )
        return None
    return notification


# --- 훅 헬퍼 (다른 앱 서비스가 호출) ------------------------------------------


def notify_like(log, actor) -> Notification | None:
    return notify(
        recipient=log.user_id,
        actor=actor,
        type=Notification.Type.LIKE,
        target_type=Notification.TargetType.CLIMB_LOG,
        target_id=log.id,
        message=f"{actor.nickname}님이 회원님의 기록을 좋아합니다",
    )


def notify_comment(comment) -> list[Notification]:
    """기록 작성자에게 comment, 답글이면 부모 댓글 작성자에게 reply (둘이 같으면 reply 만)."""
    actor = comment.user
    preview = _truncate(comment.content, PREVIEW_LENGTH)
    created = []
    parent = comment.parent
    parent_author_id = parent.user_id if parent is not None else None

    if parent_author_id is not None:
        created.append(
            notify(
                recipient=parent_author_id,
                actor=actor,
                type=Notification.Type.REPLY,
                target_type=Notification.TargetType.CLIMB_LOG,
                target_id=comment.climb_log_id,
                message=f"{actor.nickname}님이 회원님의 댓글에 답글을 남겼습니다: {preview}",
            )
        )
    log_owner_id = comment.climb_log.user_id
    if log_owner_id != parent_author_id:
        created.append(
            notify(
                recipient=log_owner_id,
                actor=actor,
                type=Notification.Type.COMMENT,
                target_type=Notification.TargetType.CLIMB_LOG,
                target_id=comment.climb_log_id,
                message=f"{actor.nickname}님이 회원님의 기록에 댓글을 남겼습니다: {preview}",
            )
        )
    return [n for n in created if n is not None]


def notify_follow(follow) -> Notification | None:
    actor = follow.follower
    return notify(
        recipient=follow.following_id,
        actor=actor,
        type=Notification.Type.FOLLOW,
        target_type=Notification.TargetType.USER,
        target_id=actor.id,
        message=f"{actor.nickname}님이 회원님을 팔로우하기 시작했습니다",
    )


def notify_recruitment_closed(recruitment, member_user_ids) -> list[Notification]:
    """마감 알림 — 승인 참여자에게 (작성자 제외). 이동 대상은 모집글(post)."""
    post = recruitment.post
    author_id = post.user_id
    title = _truncate(post.title, PREVIEW_LENGTH)
    created = []
    for user_id in dict.fromkeys(member_user_ids):
        if user_id == author_id:
            continue
        created.append(
            notify(
                recipient=user_id,
                actor=author_id,
                type=Notification.Type.RECRUITMENT_CLOSED,
                target_type=Notification.TargetType.POST,
                target_id=post.id,
                message=f"'{title}' 모집이 마감되었습니다. 채팅방에서 인사를 나눠 보세요",
            )
        )
    return [n for n in created if n is not None]


def notify_participation_status(participation) -> Notification | None:
    """승인/거절 결과를 참여자에게. 이동 대상은 모집글(post)."""
    from community.models import Participation

    post = participation.recruitment.post
    title = _truncate(post.title, PREVIEW_LENGTH)
    if participation.status == Participation.Status.APPROVED:
        type_, verb = Notification.Type.RECRUITMENT_APPROVED, "승인"
    elif participation.status == Participation.Status.REJECTED:
        type_, verb = Notification.Type.RECRUITMENT_REJECTED, "거절"
    else:
        return None
    return notify(
        recipient=participation.user_id,
        actor=post.user_id,
        type=type_,
        target_type=Notification.TargetType.POST,
        target_id=post.id,
        message=f"'{title}' 모집 참여가 {verb}되었습니다",
    )


def notify_crew_member_status(member) -> Notification | None:
    """크루 가입 승인(active) / 거절(soft delete 된 pending) 결과를 신청자에게."""
    from crews.models import CrewMember

    crew = member.crew
    if member.status == CrewMember.Status.ACTIVE and not member.is_deleted:
        type_, verb = Notification.Type.CREW_APPROVED, "승인"
    elif member.is_deleted:
        type_, verb = Notification.Type.CREW_REJECTED, "거절"
    else:
        return None
    return notify(
        recipient=member.user_id,
        actor=None,
        type=type_,
        target_type=Notification.TargetType.CREW,
        target_id=crew.id,
        message=f"{crew.name} 크루 가입이 {verb}되었습니다",
    )


def notify_crew_joined(member) -> list[Notification]:
    """가입(즉시) / 가입 신청(승인제) 을 크루장·운영진에게."""
    from crews.models import CrewMember

    crew = member.crew
    actor = member.user
    if member.status == CrewMember.Status.PENDING:
        message = f"{actor.nickname}님이 {crew.name} 크루 가입을 신청했습니다"
    else:
        message = f"{actor.nickname}님이 {crew.name} 크루에 가입했습니다"
    manager_ids = (
        CrewMember.objects.filter(
            crew=crew,
            status=CrewMember.Status.ACTIVE,
            role__in=(CrewMember.Role.OWNER, CrewMember.Role.STAFF),
        )
        .exclude(user_id=actor.id)
        .values_list("user_id", flat=True)
    )
    created = [
        notify(
            recipient=user_id,
            actor=actor,
            type=Notification.Type.CREW_JOINED,
            target_type=Notification.TargetType.CREW,
            target_id=crew.id,
            message=message,
        )
        for user_id in manager_ids
    ]
    return [n for n in created if n is not None]


# --- 조회 / 읽음 (REST) --------------------------------------------------------


def notifications_of(user, *, unread_only: bool = False):
    queryset = Notification.objects.filter(recipient=user).select_related(
        "actor__profile"
    )
    if unread_only:
        queryset = queryset.filter(is_read=False)
    return queryset.order_by("-created_at", "-id")


def unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).count()


def mark_read(notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


def mark_all_read(user) -> int:
    now = timezone.now()
    return Notification.objects.filter(recipient=user, is_read=False).update(
        is_read=True, read_at=now, updated_at=now
    )
