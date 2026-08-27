"""community 도메인 서비스 함수. 다중 모델 변경은 transaction.atomic.

정원(capacity)은 작성자를 포함한 인원이므로 "가득 참" 은
approved 참여자 수 + 1(작성자) >= capacity 로 판단한다.
"""

import logging

from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery

from community.exceptions import (
    AlreadyJoined,
    NotParticipating,
    OwnRecruitment,
    RecruitmentClosed,
    RecruitmentFull,
)
from community.models import Participation, Post, PostComment, PostImage, Recruitment
from notifications.services import (
    notify_participation_status,
    notify_recruitment_closed,
)

logger = logging.getLogger(__name__)

MAX_IMAGES = 10


# --- 조회 -------------------------------------------------------------------


def annotated_posts(user):
    """목록/상세 공용 쿼리셋 — 작성자·암장·모집 join + 댓글 수 + 모집 승인 인원/내 참여 상태.

    N+1 방지: 카드 한 장에 필요한 값을 한 쿼리(+이미지 prefetch)로 가져온다.
    """
    my_status = Participation.objects.filter(
        recruitment__post=OuterRef("pk"), user=user
    ).values("status")[:1]
    return (
        Post.objects.select_related(
            "user__profile", "gym", "recruitment__gym", "recruitment__crew"
        )
        .prefetch_related("images")
        .annotate(
            comment_count=Count(
                "comments", filter=Q(comments__is_deleted=False), distinct=True
            ),
            recruitment_approved_count=Count(
                "recruitment__participations",
                filter=Q(
                    recruitment__participations__status=Participation.Status.APPROVED,
                    recruitment__participations__is_deleted=False,
                ),
                distinct=True,
            ),
            my_participation_status=Subquery(my_status),
        )
        .order_by("-created_at")
    )


def approved_count(recruitment: Recruitment) -> int:
    return Participation.objects.filter(
        recruitment=recruitment, status=Participation.Status.APPROVED
    ).count()


def is_full(recruitment: Recruitment) -> bool:
    """작성자 1명 + 승인된 참여자가 정원에 도달했는가."""
    return approved_count(recruitment) + 1 >= recruitment.capacity


# --- 게시글 -------------------------------------------------------------------


def _replace_images(post: Post, images: list[str]) -> None:
    PostImage.objects.filter(post=post).delete()  # soft delete (bulk)
    PostImage.objects.bulk_create(
        [PostImage(post=post, image=url, order=i) for i, url in enumerate(images)]
    )


@transaction.atomic
def create_post(user, *, images=None, recruitment=None, **fields) -> Post:
    """게시글 작성. 모집글이면 Recruitment 를 함께 만든다 (serializer 가 짝을 검증)."""
    if recruitment is not None and fields.get("gym") is None:
        fields["gym"] = recruitment["gym"]  # 관련 암장 기본값 = 모집 대상 암장
    post = Post.objects.create(user=user, **fields)
    if images:
        _replace_images(post, images)
    if recruitment is not None:
        Recruitment.objects.create(post=post, **recruitment)
    return post


@transaction.atomic
def update_post(post: Post, *, images=None, recruitment=None, **fields) -> Post:
    for name, value in fields.items():
        setattr(post, name, value)
    post.save()
    if images is not None:
        _replace_images(post, images)
    if recruitment:
        rec = Recruitment.objects.select_for_update().get(post=post)
        for name, value in recruitment.items():
            setattr(rec, name, value)
        rec.save()
    return post


def increment_view_count(post: Post) -> None:
    """조회수 +1 — 경쟁 조건 없이 DB 에서 F() 로 증가."""
    Post.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)


def create_comment(
    post: Post, user, content: str, parent: PostComment | None = None
) -> PostComment:
    return PostComment.objects.create(
        post=post, user=user, content=content, parent=parent
    )


# --- 모집 ---------------------------------------------------------------------


def _lock(recruitment: Recruitment) -> Recruitment:
    """정원 계산·상태 변경 전 행 잠금 (선착순 경합 방지)."""
    return (
        Recruitment.objects.select_for_update()
        .select_related("post")
        .get(pk=recruitment.pk)
    )


@transaction.atomic
def join_recruitment(recruitment: Recruitment, user) -> Participation:
    """참여 신청 — instant 는 즉시 approved, approval 은 pending.

    Recruitment 행을 잠근 채 승인 인원을 세므로 정원을 넘길 수 없다.
    instant 에서 정원이 차면 자동 마감한다.
    """
    rec = _lock(recruitment)
    if rec.post.user_id == user.id:
        raise OwnRecruitment()
    if not rec.is_open:
        raise RecruitmentClosed()
    if Participation.objects.filter(recruitment=rec, user=user).exists():
        raise AlreadyJoined()
    if is_full(rec):
        raise RecruitmentFull()

    instant = rec.join_type == Recruitment.JoinType.INSTANT
    participation = Participation.objects.create(
        recruitment=rec,
        user=user,
        status=(
            Participation.Status.APPROVED if instant else Participation.Status.PENDING
        ),
    )
    if instant and is_full(rec):
        close_recruitment(rec)
    return participation


@transaction.atomic
def cancel_participation(recruitment: Recruitment, user) -> Participation:
    """내 참여 취소 — status=canceled 기록 후 soft delete (재참여 가능)."""
    rec = _lock(recruitment)
    participation = Participation.objects.filter(recruitment=rec, user=user).first()
    if participation is None:
        raise NotParticipating()
    if not rec.is_open:
        raise RecruitmentClosed()
    participation.status = Participation.Status.CANCELED
    participation.save(update_fields=["status", "updated_at"])
    participation.delete()
    return participation


@transaction.atomic
def set_participation_status(
    recruitment: Recruitment, participant_user_id: int, new_status: str
) -> Participation | None:
    """작성자의 승인/거절. 승인은 정원 검사 후, 정원이 차면 자동 마감.

    참여 행이 없으면 None 을 돌려준다 (뷰에서 404).
    """
    rec = _lock(recruitment)
    participation = (
        Participation.objects.select_for_update()
        .filter(recruitment=rec, user_id=participant_user_id)
        .first()
    )
    if participation is None:
        return None

    if new_status == Participation.Status.APPROVED:
        if participation.status == Participation.Status.APPROVED:
            return participation
        if not rec.is_open:
            raise RecruitmentClosed()
        if is_full(rec):
            raise RecruitmentFull()
        participation.status = Participation.Status.APPROVED
        participation.save(update_fields=["status", "updated_at"])
        notify_participation_status(participation)
        if is_full(rec):
            close_recruitment(rec)
    else:
        participation.status = Participation.Status.REJECTED
        participation.save(update_fields=["status", "updated_at"])
        notify_participation_status(participation)
    return participation


@transaction.atomic
def close_recruitment(recruitment: Recruitment) -> Recruitment:
    """모집 마감 (정원 도달 자동 / 작성자 수동). 마감 후 on_recruitment_closed 훅 호출."""
    rec = _lock(recruitment)
    if not rec.is_open:
        raise RecruitmentClosed()
    rec.status = Recruitment.Status.CLOSED
    rec.save(update_fields=["status", "updated_at"])
    on_recruitment_closed(rec)
    # 호출자가 들고 있던 인스턴스도 갱신
    recruitment.status = rec.status
    return rec


def on_recruitment_closed(recruitment: Recruitment) -> dict:
    """마감 훅 — 작성자 + 승인 참여자로 그룹 채팅방을 만들고 recruitment 에 연결한다.

    close_recruitment 의 transaction.atomic 안에서 호출된다.
    반환: {"recruitment_id", "author_id", "member_user_ids", "chat_room_id"}
    """
    author_id = recruitment.post.user_id
    approved_ids = list(
        Participation.objects.filter(
            recruitment=recruitment, status=Participation.Status.APPROVED
        )
        .order_by("created_at")
        .values_list("user_id", flat=True)
    )
    payload = {
        "recruitment_id": recruitment.id,
        "author_id": author_id,
        "member_user_ids": [author_id, *approved_ids],
    }
    logger.info("recruitment closed: %s", payload)

    # 그룹 채팅방 생성 — 작성자 + 승인된 참여자. close_recruitment 의 atomic 안이라
    # 채팅방 생성이 실패하면 마감도 함께 롤백된다.
    from chat.services import create_group_room  # 순환 import 방지용 지연 import

    gym_name = recruitment.gym.name
    room = create_group_room(
        name=f"{gym_name} 투어",
        member_ids=payload["member_user_ids"],
        created_by=recruitment.post.user,
        system_message=f"{gym_name} 투어 채팅방이 생성되었습니다",
    )
    recruitment.chat_room = room
    recruitment.save(update_fields=["chat_room", "updated_at"])
    payload["chat_room_id"] = room.id
    notify_recruitment_closed(recruitment, approved_ids)  # 작성자 제외
    return payload
