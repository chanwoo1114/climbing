"""크루 월간 통계(crews/{id}/stats/)와 전체 크루 랭킹(crews/ranking/) — crews/stats.py.

크루 피드와 같은 기준: 활동 중 크루원의 공개(is_shared) 기록만, 월은 climbed_at 기준.
"""

import datetime as dt

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.stats import shift_month
from crews.tests.helpers import add_member, create_crew, create_gym, create_log

MONTH = dt.date(2026, 8, 1)
IN_MONTH = dt.date(2026, 8, 10)
PREV_MONTH = dt.date(2026, 7, 20)


class CrewStatsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.member = create_verified_user(email="b@example.com", nickname="bravo")
        cls.applicant = create_verified_user(email="c@example.com", nickname="charlie")
        cls.outsider = create_verified_user(email="d@example.com", nickname="delta")
        cls.gym = create_gym()
        cls.gym2 = create_gym("둘째암장")

    def setUp(self):
        self.crew = create_crew(self.owner)
        add_member(self.crew, self.member)
        add_member(self.crew, self.applicant, status="pending")
        self.url = reverse("v1:crews:crew-stats", args=[self.crew.id])

        # owner: 이 달 성공 1 (다른 암장), 실패 1 / member: 이 달 성공 2, 비공개 성공 1
        create_log(self.owner, self.gym2, is_success=True, climbed_at=IN_MONTH)
        create_log(self.owner, self.gym, is_success=False, climbed_at=IN_MONTH)
        create_log(self.member, self.gym, is_success=True, climbed_at=IN_MONTH)
        create_log(self.member, self.gym, is_success=True, climbed_at=IN_MONTH)
        create_log(
            self.member, self.gym, is_success=True, is_shared=False, climbed_at=IN_MONTH
        )
        # 지난달·대기자·외부인 기록은 제외
        create_log(self.owner, self.gym, is_success=True, climbed_at=PREV_MONTH)
        create_log(self.applicant, self.gym, is_success=True, climbed_at=IN_MONTH)
        create_log(self.outsider, self.gym, is_success=True, climbed_at=IN_MONTH)

    def _get(self, user, **params):
        self.client.force_authenticate(user)
        return self.client.get(self.url, {"month": "2026-08", **params})

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_member_sees_monthly_summary_and_ranking(self):
        response = self._get(self.member)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["month"], "2026-08")
        self.assertEqual(data["member_count"], 2)  # 크루장 + 크루원 (대기자 제외)
        self.assertEqual(data["active_member_count"], 2)
        self.assertEqual(data["log_count"], 4)
        self.assertEqual(data["success_count"], 3)
        self.assertEqual(data["success_rate"], 75.0)
        self.assertEqual(data["gym_count"], 2)

        ranking = data["ranking"]
        self.assertEqual(
            [
                (r["rank"], r["user"]["nickname"], r["success_count"], r["log_count"])
                for r in ranking
            ],
            [(1, "bravo", 2, 2), (2, "alpha", 1, 2)],
        )
        self.assertEqual(ranking[0]["user"]["id"], self.member.id)
        self.assertIn("image", ranking[0]["user"])

    def test_defaults_to_current_month(self):
        self.client.force_authenticate(self.member)
        data = self.client.get(self.url).json()["data"]
        today_month = dt.date.today().replace(day=1)
        self.assertEqual(data["month"], f"{today_month:%Y-%m}")

    def test_previous_month(self):
        data = self._get(self.member, month="2026-07").json()["data"]
        self.assertEqual(data["log_count"], 1)
        self.assertEqual(data["success_count"], 1)
        self.assertEqual(data["active_member_count"], 1)
        self.assertEqual([r["user"]["nickname"] for r in data["ranking"]], ["alpha"])

    def test_empty_month(self):
        data = self._get(self.member, month="2020-01").json()["data"]
        self.assertEqual(data["log_count"], 0)
        self.assertEqual(data["success_rate"], 0.0)
        self.assertEqual(data["ranking"], [])
        self.assertEqual(data["member_count"], 2)

    def test_invalid_month_400(self):
        response = self._get(self.member, month="2026-13")
        self.assertEqual(response.status_code, 400)
        self.assertIn("month", response.json()["error"]["fields"])

    def test_ties_share_rank(self):
        create_log(self.owner, self.gym, is_success=True, climbed_at=IN_MONTH)
        # owner: 성공 2 / 기록 3, member: 성공 2 / 기록 2 → 기록 수로 owner 가 앞선다
        ranking = self._get(self.member).json()["data"]["ranking"]
        self.assertEqual([r["user"]["nickname"] for r in ranking], ["alpha", "bravo"])
        self.assertEqual([r["rank"] for r in ranking], [1, 2])

        create_log(self.member, self.gym, is_success=False, climbed_at=IN_MONTH)
        # 이제 둘 다 성공 2 / 기록 3 → 동점 → 둘 다 1위
        ranking = self._get(self.member).json()["data"]["ranking"]
        self.assertEqual([r["rank"] for r in ranking], [1, 1])

    def test_private_feed_blocks_outsider_and_applicant(self):
        self.assertEqual(self._get(self.outsider).status_code, 403)
        self.assertEqual(self._get(self.applicant).status_code, 403)

    def test_public_feed_allows_anyone(self):
        self.crew.is_feed_public = True
        self.crew.save(update_fields=["is_feed_public"])
        self.assertEqual(self._get(self.outsider).status_code, 200)

    def test_unknown_crew_404(self):
        self.client.force_authenticate(self.member)
        url = reverse("v1:crews:crew-stats", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)


class CrewRankingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = create_verified_user(email="a@example.com", nickname="alpha")
        cls.b = create_verified_user(email="b@example.com", nickname="bravo")
        cls.c = create_verified_user(email="c@example.com", nickname="charlie")
        cls.gym = create_gym()
        cls.url = reverse("v1:crews:crew-ranking")

    def setUp(self):
        self.strong = create_crew(self.a, name="강한크루", home_gym=self.gym)
        add_member(self.strong, self.b)
        self.weak = create_crew(self.c, name="약한크루")
        add_member(self.weak, self.b)  # b 는 두 크루에 모두 속한다
        self.idle = create_crew(self.b, name="쉬는크루")

        create_log(self.a, self.gym, is_success=True, climbed_at=IN_MONTH)
        create_log(
            self.a, self.gym, is_success=True, is_shared=False, climbed_at=IN_MONTH
        )
        create_log(self.b, self.gym, is_success=True, climbed_at=IN_MONTH)
        create_log(self.b, self.gym, is_success=False, climbed_at=IN_MONTH)
        create_log(self.c, self.gym, is_success=True, climbed_at=PREV_MONTH)

    def _get(self, **params):
        self.client.force_authenticate(self.c)
        return self.client.get(self.url, {"month": "2026-08", **params})

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_ranking_by_success_then_logs(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        self.assertEqual(
            [
                (
                    r["rank"],
                    r["crew"]["name"],
                    r["success_count"],
                    r["log_count"],
                    r["member_count"],
                )
                for r in rows
            ],
            [
                # strong: a 성공 1(공개만) + b 성공 1 / 기록 3, 크루원 2
                (1, "강한크루", 2, 3, 2),
                # weak: b 만 → 성공 1 / 기록 2
                (2, "약한크루", 1, 2, 2),
                # idle: b 혼자 크루장 → b 의 기록이 잡힌다 (성공 1 / 기록 2) → weak 와 동점
                (2, "쉬는크루", 1, 2, 1),
            ],
        )
        self.assertEqual(
            rows[0]["crew"]["home_gym"], {"id": self.gym.id, "name": self.gym.name}
        )
        self.assertIsNone(rows[1]["crew"]["home_gym"])

    def test_previous_month_and_limit(self):
        rows = self._get(month="2026-07").json()["data"]
        self.assertEqual(rows[0]["crew"]["name"], "약한크루")  # c 의 7월 성공
        self.assertEqual(rows[0]["success_count"], 1)

        rows = self._get(limit=1).json()["data"]
        self.assertEqual(len(rows), 1)

    def test_invalid_params_400(self):
        self.assertEqual(self._get(month="2026-8").status_code, 400)
        self.assertEqual(self._get(limit="x").status_code, 400)
        self.assertEqual(self._get(limit=0).status_code, 400)
        self.assertEqual(self._get(limit=51).status_code, 400)

    def test_deleted_crew_and_left_member_excluded(self):
        self.strong.delete()
        from crews.services import leave_crew

        leave_crew(self.weak, self.b)
        rows = self._get().json()["data"]
        names = [r["crew"]["name"] for r in rows]
        self.assertNotIn("강한크루", names)
        weak = next(r for r in rows if r["crew"]["name"] == "약한크루")
        self.assertEqual(
            (weak["success_count"], weak["log_count"], weak["member_count"]), (0, 0, 1)
        )

    def test_default_month_is_current(self):
        self.client.force_authenticate(self.c)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        this_month = dt.date.today().replace(day=1)
        self.assertEqual(shift_month(this_month, 0), this_month)
