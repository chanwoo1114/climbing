"""crews 도메인 서비스 함수. 다중 모델 변경은 transaction.atomic.

정원(max_members)은 크루장을 포함한 활동 중(active) 인원이다. 가입·승인처럼
인원이 늘어나는 구간은 Crew 행을 select_for_update 로 잠근 채 세어 정원을 넘기지 않는다.

채팅방 연동 (docs/개발정의.md 4장 크루 관련 규칙):
- 크루 생성 → 그룹 채팅방 생성 (chat.services.create_group_room)
- 가입/승인 → 채팅방 참여 + 시스템 메시지
- 탈퇴/강퇴 → 채팅방에서 제거 + 시스템 메시지
"""

from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone

from chat.services import add_members, post_system_message, remove_member
from crews.exceptions import (
    AlreadyMember,
    CannotChangeOwner,
    CrewFull,
    NotCrewMember,
    OwnerCannotLeave,
)
from crews.models import Crew, CrewMember
from notifications.services import (
    notify_crew_joined,
    notify_crew_member_status,
    notify_crew_owner_transferred,
)

DESCRIPTION_PREVIEW_LENGTH = 100


# --- 조회 -------------------------------------------------------------------


def annotated_crews(user):
    """목록/상세 공용 쿼리셋 — 홈짐·크루장 join + 활동 인원 + 내 역할/상태.

    my_role / my_member_status 는 요청자의 CrewMember 행(없으면 NULL) 에서 가져오며
    serializer 가 둘을 합쳐 my_status(owner/staff/member/pending|null) 로 내려준다.
    """
    mine = CrewMember.objects.filter(crew=OuterRef("pk"), user=user)
    return (
        Crew.objects.select_related("home_gym", "owner")
        .annotate(
            member_count=Count(
                "members",
                filter=Q(
                    members__status=CrewMember.Status.ACTIVE,
                    members__is_deleted=False,
                ),
                distinct=True,
            ),
            my_role=Subquery(mine.values("role")[:1]),
            my_member_status=Subquery(mine.values("status")[:1]),
        )
        .order_by("-created_at")
    )


def get_membership(crew, user) -> CrewMember | None:
    """요청자의 소속 행 (활동 중/대기 모두). 없으면 None."""
    return CrewMember.objects.filter(crew=crew, user=user).first()


def is_active_member(crew, user) -> bool:
    return CrewMember.objects.filter(
        crew=crew, user=user, status=CrewMember.Status.ACTIVE
    ).exists()


def active_member_user_ids(crew):
    return CrewMember.objects.filter(crew=crew, status=CrewMember.Status.ACTIVE).values(
        "user_id"
    )


def active_crews_of(user):
    """회원이 활동 중인 크루 쿼리셋 (대표 크루 선택 / 크루 주최 모집 검증용)."""
    return Crew.objects.filter(
        members__user=user,
        members__status=CrewMember.Status.ACTIVE,
        members__is_deleted=False,
    )


def active_count(crew) -> int:
    return CrewMember.objects.filter(crew=crew, status=CrewMember.Status.ACTIVE).count()


def is_full(crew) -> bool:
    return active_count(crew) >= crew.max_members


def crew_members(crew, status: str):
    return (
        CrewMember.objects.filter(crew=crew, status=status)
        .select_related("user__profile")
        .order_by("created_at", "id")
    )


def crew_feed(crew, user):
    """크루 피드 — 활동 중인 크루원들의 공개(is_shared) 기록. 권한 검사는 뷰가 한다."""
    from climbs.services import annotated_logs

    return annotated_logs(user).filter(
        is_shared=True, user_id__in=active_member_user_ids(crew)
    )


def crew_recruitments(crew, user):
    """크루 주최 모집글 (Recruitment.crew == crew)."""
    from community.services import annotated_posts

    return annotated_posts(user).filter(recruitment__crew=crew)


# --- 크루 -------------------------------------------------------------------


def _lock(crew) -> Crew:
    """정원 계산·상태 변경 전 행 잠금 (가입 경합 방지)."""
    return Crew.objects.select_for_update().get(pk=crew.pk)


def _reset_main_crew(user_id: int, crew) -> None:
    """탈퇴·강퇴로 크루를 떠난 회원의 대표 크루가 이 크루면 비운다."""
    from accounts.models import UserProfile

    UserProfile.objects.filter(user_id=user_id, main_crew=crew).update(main_crew=None)


@transaction.atomic
def create_crew(owner, **fields) -> Crew:
    """크루 생성 — 단톡방 생성 + 크루장 소속 행을 한 트랜잭션에서."""
    from chat.services import create_group_room

    name = fields["name"]
    room = create_group_room(
        name=name,
        member_ids=[],
        created_by=owner,
        system_message=f"{name} 크루 채팅방이 생성되었습니다",
    )
    crew = Crew.objects.create(owner=owner, chat_room=room, **fields)
    CrewMember.objects.create(
        crew=crew,
        user=owner,
        role=CrewMember.Role.OWNER,
        status=CrewMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    return crew


@transaction.atomic
def update_crew(crew: Crew, **fields) -> Crew:
    for name, value in fields.items():
        setattr(crew, name, value)
    crew.save()
    if "name" in fields and crew.chat_room.name != crew.name:
        crew.chat_room.name = crew.name  # 단톡방 이름도 따라간다
        crew.chat_room.save(update_fields=["name", "updated_at"])
    return crew


@transaction.atomic
def delete_crew(crew: Crew) -> None:
    """크루 삭제 (soft). 소속 행은 cascade, 대표 크루 참조는 비운다. 단톡방은 그대로 둔다."""
    from accounts.models import UserProfile

    UserProfile.objects.filter(main_crew=crew).update(main_crew=None)
    crew.delete()


# --- 가입 / 탈퇴 -------------------------------------------------------------


def _welcome(crew: Crew, member: CrewMember) -> None:
    """활동 시작 — 단톡방 참여 + 시스템 메시지."""
    add_members(crew.chat_room, [member.user_id])
    post_system_message(crew.chat_room, f"{member.user.nickname}님이 가입했습니다")


@transaction.atomic
def join_crew(crew: Crew, user) -> CrewMember:
    """가입 신청 — instant 는 즉시 active(+단톡방), approval 은 pending.

    Crew 행을 잠근 채 활동 인원을 세므로 정원을 넘길 수 없다.
    """
    crew = _lock(crew)
    if CrewMember.objects.filter(crew=crew, user=user).exists():
        raise AlreadyMember()
    if is_full(crew):
        raise CrewFull()

    instant = crew.join_type == Crew.JoinType.INSTANT
    member = CrewMember.objects.create(
        crew=crew,
        user=user,
        role=CrewMember.Role.MEMBER,
        status=(CrewMember.Status.ACTIVE if instant else CrewMember.Status.PENDING),
        joined_at=timezone.now() if instant else None,
    )
    if instant:
        _welcome(crew, member)
    notify_crew_joined(member)  # 크루장·운영진에게 가입/신청 알림
    return member


@transaction.atomic
def leave_crew(crew: Crew, user) -> CrewMember:
    """탈퇴 — 활동 중이면 단톡방에서도 나가고, 대기 중이면 신청만 취소한다."""
    membership = get_membership(crew, user)
    if membership is None:
        raise NotCrewMember()
    if membership.role == CrewMember.Role.OWNER:
        raise OwnerCannotLeave()

    was_active = membership.status == CrewMember.Status.ACTIVE
    membership.delete()
    if was_active:
        remove_member(crew.chat_room, user, f"{user.nickname}님이 나갔습니다")
    _reset_main_crew(user.id, crew)
    return membership


# --- 크루원 관리 (크루장/운영진) ------------------------------------------------


@transaction.atomic
def set_member_status(crew: Crew, target_user_id: int, new_status: str):
    """승인 대기 중인 신청을 승인(active) / 거절(rejected, soft delete).

    승인은 정원 검사 후 단톡방에 참여시킨다. 대기 행이 없으면 None (뷰에서 404).
    """
    crew = _lock(crew)
    member = (
        CrewMember.objects.select_for_update(of=("self",))
        .select_related("user")
        .filter(crew=crew, user_id=target_user_id, status=CrewMember.Status.PENDING)
        .first()
    )
    if member is None:
        return None

    if new_status == CrewMember.Status.ACTIVE:
        if is_full(crew):
            raise CrewFull()
        member.status = CrewMember.Status.ACTIVE
        member.joined_at = timezone.now()
        member.save(update_fields=["status", "joined_at", "updated_at"])
        _welcome(crew, member)
    else:
        member.delete()
    notify_crew_member_status(member)  # 승인/거절 결과를 신청자에게
    return member


@transaction.atomic
def set_member_role(crew: Crew, target_user_id: int, role: str):
    """활동 중인 크루원의 역할 변경 (staff ↔ member). 크루장은 바꿀 수 없다."""
    member = (
        CrewMember.objects.select_for_update()
        .select_related("user")
        .filter(crew=crew, user_id=target_user_id, status=CrewMember.Status.ACTIVE)
        .first()
    )
    if member is None:
        return None
    if member.role == CrewMember.Role.OWNER:
        raise CannotChangeOwner()
    member.role = role
    member.save(update_fields=["role", "updated_at"])
    return member


@transaction.atomic
def transfer_ownership(crew: Crew, target_user_id: int, actor) -> Crew:
    """크루장 위임 — 새 크루장(활동 중 크루원)은 owner, 기존 크루장은 staff 로.

    권한(요청자가 크루장) 검사는 뷰가 한다. 크루장이 크루를 떠나거나 탈퇴하려면
    먼저 위임해야 한다 (leave_crew: OwnerCannotLeave, accounts.withdraw_user: 409).
    """
    from rest_framework import serializers as drf_serializers

    crew = _lock(crew)
    if target_user_id == crew.owner_id:
        raise drf_serializers.ValidationError({"user_id": ["이미 크루장입니다."]})
    new_owner = (
        CrewMember.objects.select_for_update()
        .select_related("user")
        .filter(crew=crew, user_id=target_user_id, status=CrewMember.Status.ACTIVE)
        .first()
    )
    if new_owner is None:
        raise drf_serializers.ValidationError(
            {"user_id": ["활동 중인 크루원에게만 위임할 수 있습니다."]}
        )
    old_owner = CrewMember.objects.select_for_update().get(
        crew=crew, user_id=crew.owner_id, status=CrewMember.Status.ACTIVE
    )
    old_owner.role = CrewMember.Role.STAFF
    old_owner.save(update_fields=["role", "updated_at"])
    new_owner.role = CrewMember.Role.OWNER
    new_owner.save(update_fields=["role", "updated_at"])
    crew.owner = new_owner.user
    crew.save(update_fields=["owner", "updated_at"])
    notify_crew_owner_transferred(crew, actor)
    return crew


@transaction.atomic
def kick_member(crew: Crew, member: CrewMember) -> CrewMember:
    """강퇴 — 소속 행 soft delete + 단톡방 제거 + 시스템 메시지 + 대표 크루 해제.

    권한(크루장/운영진, 운영진은 크루원만) 검사는 뷰가 한다.
    """
    was_active = member.status == CrewMember.Status.ACTIVE
    member.delete()
    if was_active:
        remove_member(
            crew.chat_room, member.user, f"{member.user.nickname}님이 내보내졌습니다"
        )
    _reset_main_crew(member.user_id, crew)
    return member
