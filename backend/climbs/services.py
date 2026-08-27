"""climbs 도메인 서비스 함수. 다중 모델 변경은 transaction.atomic."""

from django.apps import apps
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q

from climbs.models import ClimbLog, ClimbLogComment, ClimbLogLike
from notifications.services import notify_comment, notify_like


def annotated_logs(user):
    """목록/상세 공용 쿼리셋 — 작성자·암장·난이도 join + 좋아요/댓글 수 + 내 좋아요 여부.

    N+1 방지: 카드 한 장에 필요한 값을 전부 한 쿼리로 가져온다.
    """
    return (
        ClimbLog.objects.select_related("user__profile", "gym", "difficulty")
        .annotate(
            like_count=Count("likes", filter=Q(likes__is_deleted=False), distinct=True),
            comment_count=Count(
                "comments", filter=Q(comments__is_deleted=False), distinct=True
            ),
            is_liked=Exists(
                ClimbLogLike.objects.filter(climb_log=OuterRef("pk"), user=user)
            ),
        )
        .order_by("-created_at")
    )


def visible_logs(user):
    """요청자가 볼 수 있는 기록 — 본인 것 전부 + 남의 공개(is_shared) 기록."""
    return annotated_logs(user).filter(Q(user=user) | Q(is_shared=True))


def following_user_ids(user):
    """팔로우 중인 회원 id 쿼리셋. social.Follow 가 아직 없으면 빈 목록."""
    try:
        Follow = apps.get_model("social", "Follow")
    except LookupError:
        return []
    return Follow.objects.filter(follower=user).values("following_id")


def feed_logs(user, scope="explore"):
    queryset = annotated_logs(user).filter(is_shared=True)
    if scope == "following":
        return queryset.filter(user_id__in=following_user_ids(user))
    return queryset


@transaction.atomic
def like_log(log: ClimbLog, user) -> ClimbLogLike:
    """좋아요 — 멱등. 취소(soft delete)했던 행이 있으면 복구한다."""
    like, created = ClimbLogLike.all_objects.get_or_create(climb_log=log, user=user)
    if not created and like.is_deleted:
        like.restore()
        created = True
    if created:  # 새 좋아요/복구일 때만 알림 (같은 사람 반복은 notify 가 정리)
        notify_like(log, user)
    return like


def unlike_log(log: ClimbLog, user) -> bool:
    """좋아요 취소 — 없어도 성공(멱등). soft delete."""
    deleted = ClimbLogLike.objects.filter(climb_log=log, user=user).delete()
    return bool(deleted)


def create_comment(
    log: ClimbLog, user, content: str, parent: ClimbLogComment | None = None
) -> ClimbLogComment:
    comment = ClimbLogComment.objects.create(
        climb_log=log, user=user, content=content, parent=parent
    )
    notify_comment(comment)  # 기록 작성자(comment) + 부모 댓글 작성자(reply)
    return comment
