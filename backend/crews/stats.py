"""크루 통계 / 랭킹 (M8, M6 에서 이월).

- crew_stats(crew, month): 그 달 크루원(활동 중)들의 공개 기록 집계 + 크루원 활동 랭킹
- crew_ranking(month, limit): 전체 크루를 그 달 완등 수로 줄 세운 랭킹

크루 피드와 같은 기준으로 공개(is_shared) 기록만 센다 — 비공개 기록은 본인만 볼 수 있으니
크루 통계에도 섞지 않는다. 월은 climbed_at(등반한 날짜) 기준.
"""

import datetime as dt

from django.db.models import Count, Q

from climbs.models import ClimbLog
from climbs.stats import logs_in_month, month_bounds, month_key, success_rate
from crews.models import Crew, CrewMember
from crews.services import active_count, active_member_user_ids

MEMBER_RANKING_LIMIT = 10
CREW_RANKING_DEFAULT_LIMIT = 20
CREW_RANKING_MAX_LIMIT = 50


def _rank(rows: list[dict]) -> list[dict]:
    """정렬된 행에 1부터 순위를 붙인다. 동점은 같은 순위, 다음 순위는 건너뛴다 (1,1,3)."""
    ranked = []
    previous_key = None
    rank = 0
    for index, row in enumerate(rows, start=1):
        key = (row["success_count"], row["log_count"])
        if key != previous_key:
            rank = index
            previous_key = key
        ranked.append({"rank": rank, **row})
    return ranked


def crew_stats(crew: Crew, first_day: dt.date) -> dict:
    """그 달 크루 활동 요약 + 크루원 랭킹(완등 수 → 기록 수 → 회원 id)."""
    logs = logs_in_month(
        ClimbLog.objects.filter(
            is_shared=True, user_id__in=active_member_user_ids(crew)
        ),
        first_day,
    )
    totals = logs.aggregate(
        log_count=Count("id"),
        success_count=Count("id", filter=Q(is_success=True)),
        active_member_count=Count("user", distinct=True),
        gym_count=Count("gym", distinct=True),
    )
    rows = (
        logs.values("user_id", "user__nickname", "user__profile__image")
        .annotate(
            log_count=Count("id"),
            success_count=Count("id", filter=Q(is_success=True)),
        )
        .order_by("-success_count", "-log_count", "user_id")[:MEMBER_RANKING_LIMIT]
    )
    ranking = _rank(
        [
            {
                "user": {
                    "id": row["user_id"],
                    "nickname": row["user__nickname"],
                    "image": row["user__profile__image"] or None,
                },
                "log_count": row["log_count"],
                "success_count": row["success_count"],
            }
            for row in rows
        ]
    )
    return {
        "month": month_key(first_day),
        "member_count": active_count(crew),
        "active_member_count": totals["active_member_count"],
        "log_count": totals["log_count"],
        "success_count": totals["success_count"],
        "success_rate": success_rate(totals["log_count"], totals["success_count"]),
        "gym_count": totals["gym_count"],
        "ranking": ranking,
    }


def crew_ranking(first_day: dt.date, limit: int = CREW_RANKING_DEFAULT_LIMIT) -> list:
    """전체 크루 랭킹 — 그 달 활동 중 크루원들의 공개 완등 수 → 기록 수 → 크루 id.

    기록이 없는 크루도 0 으로 포함되어 뒤에 붙는다 (limit 안에서).
    """
    start, end = month_bounds(first_day)
    active_member = Q(
        members__status=CrewMember.Status.ACTIVE, members__is_deleted=False
    )
    month_log = active_member & Q(
        members__user__climb_logs__is_deleted=False,
        members__user__climb_logs__is_shared=True,
        members__user__climb_logs__climbed_at__gte=start,
        members__user__climb_logs__climbed_at__lt=end,
    )
    crews = (
        Crew.objects.select_related("home_gym")
        .annotate(
            member_count=Count("members", filter=active_member, distinct=True),
            log_count=Count(
                "members__user__climb_logs", filter=month_log, distinct=True
            ),
            success_count=Count(
                "members__user__climb_logs",
                filter=month_log & Q(members__user__climb_logs__is_success=True),
                distinct=True,
            ),
        )
        .order_by("-success_count", "-log_count", "id")[:limit]
    )
    return _rank(
        [
            {
                "crew": {
                    "id": crew.id,
                    "name": crew.name,
                    "image": crew.image or None,
                    "home_gym": (
                        {"id": crew.home_gym.id, "name": crew.home_gym.name}
                        if crew.home_gym_id
                        else None
                    ),
                },
                "member_count": crew.member_count,
                "log_count": crew.log_count,
                "success_count": crew.success_count,
            }
            for crew in crews
        ]
    )
