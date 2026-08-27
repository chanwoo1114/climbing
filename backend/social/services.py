"""social 도메인 서비스 함수. 다중 모델 변경은 transaction.atomic."""

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from rest_framework.generics import get_object_or_404

from accounts.models import User
from notifications.services import notify_follow
from social.exceptions import SelfFollowNotAllowed
from social.models import Follow


@transaction.atomic
def follow_user(*, follower: User, target_id: int) -> Follow:
    """팔로우. 이미 팔로우 중이면 그대로 반환한다 (멱등)."""
    if follower.pk == target_id:
        raise SelfFollowNotAllowed()
    # objects 는 탈퇴(soft delete) 회원을 제외하므로 탈퇴 회원은 404.
    target = get_object_or_404(User, pk=target_id)

    # all_objects: soft delete 된 행이 남아 있으면 UNIQUE 에 걸리므로 복구해서 재사용.
    follow, created = Follow.all_objects.get_or_create(
        follower=follower, following=target
    )
    if not created and follow.is_deleted:
        follow.restore()
        created = True
    if created:  # 이미 팔로우 중이면 알림 없음
        notify_follow(follow)
    return follow


def unfollow_user(*, follower: User, target_id: int) -> None:
    """언팔로우. 팔로우 중이 아니어도 조용히 성공한다 (멱등)."""
    get_object_or_404(User, pk=target_id)
    Follow.all_objects.filter(follower=follower, following_id=target_id).hard_delete()


def followers_of(user_id: int) -> QuerySet[Follow]:
    """user 를 팔로우하는 관계 목록 (탈퇴 회원 제외). 최근 팔로우 순."""
    return (
        Follow.objects.filter(following_id=user_id, follower__is_deleted=False)
        .select_related("follower", "follower__profile")
        .order_by("-created_at", "-id")
    )


def following_of(user_id: int) -> QuerySet[Follow]:
    """user 가 팔로우하는 관계 목록 (탈퇴 회원 제외). 최근 팔로우 순."""
    return (
        Follow.objects.filter(follower_id=user_id, following__is_deleted=False)
        .select_related("following", "following__profile")
        .order_by("-created_at", "-id")
    )


def following_ids(requester: User, user_ids) -> set[int]:
    """user_ids 중 requester 가 팔로우 중인 id 집합 (목록의 is_following 계산용)."""
    if not user_ids or not requester.is_authenticated:
        return set()
    return set(
        Follow.objects.filter(
            follower=requester, following_id__in=user_ids
        ).values_list("following_id", flat=True)
    )


def annotate_follow_stats(queryset: QuerySet[User], requester: User) -> QuerySet[User]:
    """User 쿼리셋에 follower_count / following_count / is_following 을 붙인다.

    프로필 상세처럼 한 건 조회에 쓴다. Count 두 개가 JOIN 을 겹치므로 distinct.
    """
    is_following = Follow.objects.filter(
        follower_id=requester.pk if requester.is_authenticated else None,
        following_id=OuterRef("pk"),
    )
    return queryset.annotate(
        follower_count=Count(
            "follower_set",
            filter=Q(
                follower_set__is_deleted=False,
                follower_set__follower__is_deleted=False,
            ),
            distinct=True,
        ),
        following_count=Count(
            "following_set",
            filter=Q(
                following_set__is_deleted=False,
                following_set__following__is_deleted=False,
            ),
            distinct=True,
        ),
        is_following=Exists(is_following),
    )
