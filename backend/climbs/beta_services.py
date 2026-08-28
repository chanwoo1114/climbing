"""베타 영상(ClimbBeta) 쿼리 헬퍼 — 뷰는 얇게, 조회/집계 로직은 여기에."""

from django.db.models import Count, F

from climbs.models import ClimbBeta


def annotated_betas():
    """목록/상세 공용 쿼리셋 — 올린 사람·암장·난이도 join, 최신순."""
    return ClimbBeta.objects.select_related(
        "user__profile", "gym", "difficulty"
    ).order_by("-created_at")


def gym_betas(gym, *, sector=None, difficulty_id=None, q=None):
    """암장의 베타 목록. 섹터는 대소문자 무시 완전일치, q 는 제목 부분일치."""
    queryset = annotated_betas().filter(gym=gym)
    if sector:
        queryset = queryset.filter(sector__iexact=sector)
    if difficulty_id is not None:
        queryset = queryset.filter(difficulty_id=difficulty_id)
    if q:
        queryset = queryset.filter(title__icontains=q)
    return queryset


def beta_sectors(gym) -> list[dict]:
    """암장의 섹터별 베타 개수 — 빈 섹터 제외, 개수 내림차순 → 이름순."""
    rows = (
        ClimbBeta.objects.filter(gym=gym)
        .exclude(sector="")
        .values("sector")
        .annotate(count=Count("id"))
        .order_by("-count", "sector")
    )
    return [{"sector": row["sector"], "count": row["count"]} for row in rows]


def increment_view_count(beta: ClimbBeta) -> int:
    """조회수 +1 — 동시 요청에도 값이 유실되지 않도록 F() 로 DB 에서 증가시킨다."""
    ClimbBeta.objects.filter(pk=beta.pk).update(view_count=F("view_count") + 1)
    beta.refresh_from_db(fields=["view_count"])
    return beta.view_count
