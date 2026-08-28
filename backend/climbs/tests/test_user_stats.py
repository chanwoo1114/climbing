"""회원 통계 — users/{id}/stats/ (climbs/stats.py).

본인은 전체 기록, 타인은 공개 기록만. 성공률·난이도 분포·최근 12개월 추이·자주 간 암장.
"""

import datetime as dt

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.stats import monthly_trend, parse_month, shift_month, success_rate
from climbs.models import ClimbLog
from climbs.tests.helpers import create_difficulty, create_gym, create_log
from rest_framework.exceptions import ValidationError


class UserStatsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="o@example.com", nickname="owner")
        cls.other = create_verified_user(email="x@example.com", nickname="other")
        cls.gym = create_gym("가암장")
        cls.gym2 = create_gym("나암장")
        cls.green = create_difficulty(cls.gym, "초록", "#5f7d4e", 0)
        cls.blue = create_difficulty(cls.gym, "파랑", "#2456d6", 1)
        cls.url = reverse("v1:climbs:user-stats", args=[cls.owner.id])

    def setUp(self):
        today = timezone.localdate()
        # 공개: 초록 성공 2, 초록 실패 1, 파랑 성공 1 (다른 암장, 난이도 없음)
        create_log(self.owner, self.gym, difficulty=self.green, is_success=True)
        create_log(self.owner, self.gym, difficulty=self.green, is_success=True)
        create_log(
            self.owner, self.gym, difficulty=self.green, is_success=False, attempts=5
        )
        create_log(self.owner, self.gym2, is_success=True, attempts=1)
        # 비공개 파랑 성공 — 본인만 집계
        create_log(
            self.owner,
            self.gym,
            difficulty=self.blue,
            is_success=True,
            is_shared=False,
        )
        # 두 달 전 기록 — this_month 에 안 잡히고 by_month 에는 잡힌다
        create_log(
            self.owner,
            self.gym,
            is_success=False,
            climbed_at=shift_month(today.replace(day=1), -2),
        )
        # 남의 기록은 섞이지 않는다
        create_log(self.other, self.gym, difficulty=self.green, is_success=True)

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_other_sees_shared_only(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["total_count"], 5)
        self.assertEqual(data["success_count"], 3)
        self.assertEqual(data["success_rate"], 60.0)
        self.assertEqual(data["gym_count"], 2)
        self.assertEqual(data["avg_attempts"], round((2 + 2 + 5 + 1 + 2) / 5, 1))

        self.assertEqual(data["this_month"]["total_count"], 4)
        self.assertEqual(data["this_month"]["success_count"], 3)

        # 난이도 분포 — 비공개 파랑은 빠지고, 난이도 없는 기록도 빠진다
        self.assertEqual(len(data["by_difficulty"]), 1)
        row = data["by_difficulty"][0]
        self.assertEqual(row["gym"], {"id": self.gym.id, "name": "가암장"})
        self.assertEqual(row["difficulty"]["name"], "초록")
        self.assertEqual(row["difficulty"]["color"], "#5f7d4e")
        self.assertEqual((row["total_count"], row["success_count"]), (3, 2))
        self.assertEqual(row["success_rate"], 66.7)

        # 자주 간 암장 — 기록 수 내림차순
        self.assertEqual(
            [(g["gym"]["name"], g["total_count"]) for g in data["top_gyms"]],
            [("가암장", 4), ("나암장", 1)],
        )

    def test_owner_sees_all_including_private(self):
        self.client.force_authenticate(self.owner)
        data = self.client.get(self.url).json()["data"]
        self.assertEqual(data["total_count"], 6)
        self.assertEqual(data["success_count"], 4)
        names = [row["difficulty"]["name"] for row in data["by_difficulty"]]
        self.assertEqual(names, ["초록", "파랑"])  # 난이도 order 순

    def test_by_month_covers_last_12_months_oldest_first(self):
        self.client.force_authenticate(self.other)
        by_month = self.client.get(self.url).json()["data"]["by_month"]
        self.assertEqual(len(by_month), 12)

        this_month = timezone.localdate().replace(day=1)
        self.assertEqual(by_month[-1]["month"], f"{this_month:%Y-%m}")
        self.assertEqual(by_month[0]["month"], f"{shift_month(this_month, -11):%Y-%m}")
        self.assertEqual(by_month[-1]["total_count"], 4)
        self.assertEqual(by_month[-3]["total_count"], 1)  # 두 달 전 실패 1
        self.assertEqual(by_month[-3]["success_count"], 0)
        self.assertEqual(by_month[-2]["total_count"], 0)  # 빈 달은 0 으로 채움

    def test_empty_stats(self):
        self.client.force_authenticate(self.other)
        url = reverse("v1:climbs:user-stats", args=[self.other.id])
        # other 의 공개 기록 1건을 지워 빈 상태로
        ClimbLog.objects.filter(user=self.other).delete()
        data = self.client.get(url).json()["data"]
        self.assertEqual(data["total_count"], 0)
        self.assertEqual(data["success_rate"], 0.0)
        self.assertIsNone(data["avg_attempts"])
        self.assertEqual(data["by_difficulty"], [])
        self.assertEqual(data["top_gyms"], [])
        self.assertEqual(len(data["by_month"]), 12)

    def test_unknown_or_withdrawn_user_404(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(reverse("v1:climbs:user-stats", args=[999999])).status_code,
            404,
        )
        self.owner.delete()
        self.assertEqual(self.client.get(self.url).status_code, 404)


class StatsHelperTests(APITestCase):
    def test_success_rate(self):
        self.assertEqual(success_rate(0, 0), 0.0)
        self.assertEqual(success_rate(3, 2), 66.7)
        self.assertEqual(success_rate(4, 4), 100.0)

    def test_shift_month_across_year(self):
        self.assertEqual(shift_month(dt.date(2026, 1, 1), -1), dt.date(2025, 12, 1))
        self.assertEqual(shift_month(dt.date(2026, 12, 1), 1), dt.date(2027, 1, 1))
        self.assertEqual(shift_month(dt.date(2026, 8, 1), -11), dt.date(2025, 9, 1))

    def test_parse_month(self):
        self.assertEqual(parse_month("2026-02"), dt.date(2026, 2, 1))
        self.assertEqual(parse_month(None), timezone.localdate().replace(day=1))
        for bad in ("2026-13", "2026-1", "202601", "abc"):
            with self.assertRaises(ValidationError):
                parse_month(bad)

    def test_monthly_trend_fills_gaps(self):
        user = create_verified_user(email="t@example.com", nickname="trend")
        gym = create_gym()
        create_log(user, gym, climbed_at=dt.date(2026, 3, 15))
        trend = monthly_trend(
            ClimbLog.objects.filter(user=user), until=dt.date(2026, 5, 1), months=3
        )
        self.assertEqual([t["month"] for t in trend], ["2026-03", "2026-04", "2026-05"])
        self.assertEqual([t["total_count"] for t in trend], [1, 0, 0])
