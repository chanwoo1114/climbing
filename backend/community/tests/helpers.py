"""community 테스트 공용 헬퍼 — 게시글/모집/참여 생성."""

from datetime import timedelta

from django.utils import timezone

from climbs.tests.helpers import create_gym  # noqa: F401  (재노출)
from community.models import Participation, Post, Recruitment


def create_post(user, **kwargs) -> Post:
    defaults = {"category": Post.Category.FREE, "title": "제목", "content": "본문"}
    defaults.update(kwargs)
    return Post.objects.create(user=user, **defaults)


def create_recruit_post(user, gym, capacity=3, join_type="instant", **kwargs) -> Post:
    """모집글 + Recruitment. 반환된 post.recruitment 로 접근."""
    post = create_post(
        user, category=Post.Category.RECRUIT, gym=gym, title="투어 모집", **kwargs
    )
    Recruitment.objects.create(
        post=post,
        gym=gym,
        meet_at=timezone.now() + timedelta(days=3),
        capacity=capacity,
        join_type=join_type,
    )
    return post


def add_participant(post, user, status="approved") -> Participation:
    return Participation.objects.create(
        recruitment=post.recruitment, user=user, status=status
    )


def future_iso(days=3) -> str:
    return (timezone.now() + timedelta(days=days)).isoformat()
