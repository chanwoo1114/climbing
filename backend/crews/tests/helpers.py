"""crews 테스트 공용 헬퍼 — 크루/소속 생성."""

from django.utils import timezone

from chat.services import add_members
from climbs.tests.helpers import create_gym, create_log  # noqa: F401  (재노출)
from crews.models import Crew, CrewMember
from crews.services import create_crew as _create_crew


def create_crew(owner, name="테스트크루", **kwargs) -> Crew:
    """서비스 경유 생성 — 단톡방 + 크루장 소속 행까지 실제 흐름 그대로."""
    return _create_crew(owner, name=name, **kwargs)


def add_member(crew, user, role="member", status="active") -> CrewMember:
    """소속 행 직접 생성. 활동 중이면 실제 가입 흐름처럼 단톡방에도 넣는다."""
    member = CrewMember.objects.create(
        crew=crew,
        user=user,
        role=role,
        status=status,
        joined_at=timezone.now() if status == "active" else None,
    )
    if status == "active":
        add_members(crew.chat_room, [user.id])
    return member
