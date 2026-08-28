"""등반 기록 통계 (M3 프로필 통계 / M8 크루 통계의 공용 집계).

모든 집계는 DB 에서 GROUP BY 로 끝내고 파이썬은 월 채우기·비율 계산만 한다.
성공률은 0~100 (소수 1자리), 기록이 없으면 0.0.
"""

import calendar
import datetime as dt
import re

from django.db.models import Avg, Count, Q, QuerySet
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from climbs.models import ClimbLog

MONTHS_IN_TREND = 12
TOP_GYMS_LIMIT = 5
MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def month_key(day: dt.date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def parse_month(value: str | None) -> dt.date:
    """'YYYY-MM' → 그 달 1일. 없으면 이번 달(Asia/Seoul 기준). 형식이 틀리면 400."""
    if not value:
        today = timezone.localdate()
        return today.replace(day=1)
    match = MONTH_PATTERN.match(value)
    if match is None:
        raise ValidationError({"month": ["month 는 YYYY-MM 형식이어야 합니다."]})
    return dt.date(int(match.group(1)), int(match.group(2)), 1)


def month_bounds(first_day: dt.date) -> tuple[dt.date, dt.date]:
    """[그 달 1일, 다음 달 1일) — climbed_at 범위 필터용."""
    last = calendar.monthrange(first_day.year, first_day.month)[1]
    return first_day, first_day.replace(day=last) + dt.timedelta(days=1)


def shift_month(first_day: dt.date, delta: int) -> dt.date:
    index = first_day.year * 12 + (first_day.month - 1) + delta
    return dt.date(index // 12, index % 12 + 1, 1)


def success_rate(total: int, success: int) -> float:
    return round(success * 100 / total, 1) if total else 0.0


def logs_in_month(queryset: QuerySet[ClimbLog], first_day: dt.date):
    start, end = month_bounds(first_day)
    return queryset.filter(climbed_at__gte=start, climbed_at__lt=end)


def _count_success():
    return Count("id", filter=Q(is_success=True))


def summarize(queryset: QuerySet[ClimbLog]) -> dict:
    """총 기록 수 / 완등 수 / 성공률 / 방문 암장 수 / 평균 시도 횟수."""
    row = queryset.aggregate(
        total_count=Count("id"),
        success_count=_count_success(),
        gym_count=Count("gym", distinct=True),
        avg_attempts=Avg("attempts"),
    )
    total, success = row["total_count"], row["success_count"]
    return {
        "total_count": total,
        "success_count": success,
        "success_rate": success_rate(total, success),
        "gym_count": row["gym_count"],
        "avg_attempts": (
            round(row["avg_attempts"], 1) if row["avg_attempts"] is not None else None
        ),
    }


def monthly_trend(
    queryset: QuerySet[ClimbLog], *, until: dt.date, months: int = MONTHS_IN_TREND
) -> list[dict]:
    """until 달까지 최근 `months` 개월, 기록이 없는 달은 0 으로 채워 오래된 달부터."""
    first = shift_month(until, -(months - 1))
    start, _ = month_bounds(first)
    _, end = month_bounds(until)
    rows = (
        queryset.filter(climbed_at__gte=start, climbed_at__lt=end)
        .annotate(month=TruncMonth("climbed_at"))
        .values("month")
        .annotate(total_count=Count("id"), success_count=_count_success())
    )
    by_key = {month_key(row["month"]): row for row in rows}
    trend = []
    for offset in range(months):
        key = month_key(shift_month(first, offset))
        row = by_key.get(key)
        trend.append(
            {
                "month": key,
                "total_count": row["total_count"] if row else 0,
                "success_count": row["success_count"] if row else 0,
            }
        )
    return trend


def by_difficulty(queryset: QuerySet[ClimbLog]) -> list[dict]:
    """암장·난이도별 시도/완등 수. 난이도가 없는 기록은 제외. 암장 이름 → 난이도 순."""
    rows = (
        queryset.filter(difficulty__isnull=False)
        .values(
            "gym_id",
            "gym__name",
            "difficulty_id",
            "difficulty__name",
            "difficulty__color",
            "difficulty__order",
        )
        .annotate(total_count=Count("id"), success_count=_count_success())
        .order_by("gym__name", "gym_id", "difficulty__order", "difficulty_id")
    )
    return [
        {
            "gym": {"id": row["gym_id"], "name": row["gym__name"]},
            "difficulty": {
                "id": row["difficulty_id"],
                "name": row["difficulty__name"],
                "color": row["difficulty__color"],
                "order": row["difficulty__order"],
            },
            "total_count": row["total_count"],
            "success_count": row["success_count"],
            "success_rate": success_rate(row["total_count"], row["success_count"]),
        }
        for row in rows
    ]


def top_gyms(queryset: QuerySet[ClimbLog], limit: int = TOP_GYMS_LIMIT) -> list[dict]:
    """자주 간 암장 — 기록 수 내림차순."""
    rows = (
        queryset.values("gym_id", "gym__name")
        .annotate(total_count=Count("id"), success_count=_count_success())
        .order_by("-total_count", "gym_id")[:limit]
    )
    return [
        {
            "gym": {"id": row["gym_id"], "name": row["gym__name"]},
            "total_count": row["total_count"],
            "success_count": row["success_count"],
        }
        for row in rows
    ]


def user_stats(owner, requester) -> dict:
    """프로필 통계 — 본인이면 전체, 타인이면 공개(is_shared) 기록만 집계."""
    logs = ClimbLog.objects.filter(user=owner)
    if requester.pk != owner.pk:
        logs = logs.filter(is_shared=True)

    this_month = timezone.localdate().replace(day=1)
    month_summary = logs_in_month(logs, this_month).aggregate(
        total_count=Count("id"), success_count=_count_success()
    )
    return {
        **summarize(logs),
        "this_month": {"month": month_key(this_month), **month_summary},
        "by_month": monthly_trend(logs, until=this_month),
        "by_difficulty": by_difficulty(logs),
        "top_gyms": top_gyms(logs),
    }
