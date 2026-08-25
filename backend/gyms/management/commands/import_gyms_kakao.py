"""Kakao Local API로 전국 클라이밍장을 수집해 DB에 적재한다.

카카오는 검색 결과를 최대 45건(3페이지)까지만 주므로, 전국을 격자로 쪼개
사각형(rect) 검색을 반복한다. 45건이 꽉 차면 그 격자를 4등분해 재귀 탐색.

사용법:
  1. https://developers.kakao.com 에서 앱 생성 → REST API 키 발급 (무료)
  2. backend/.env 에 KAKAO_REST_API_KEY=<키> 추가
  3. dc exec web python manage.py import_gyms_kakao
"""

import time

import environ
import urllib.parse
import urllib.request
import json as jsonlib

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from gyms.models import Gym, GymDifficulty

API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
PAGE_SIZE = 15
MAX_PAGES = 3  # 카카오 제한: 페이지당 15건 × 3페이지 = 45건

# 남한 전역 (제주 포함) — lng_min, lat_min, lng_max, lat_max
KOREA_BBOX = (124.5, 33.0, 131.0, 38.7)

# 검색어별로 훑는다 (상호에 '클라이밍'이 없는 곳 보완)
KEYWORDS = ["클라이밍", "볼더링", "암벽등반"]

# 클라이밍장이 아닌 결과 제외 (용품점, 학원 등)
EXCLUDE_TOKENS = ("용품", "장비", "샵", "웨어", "아웃도어")

DEFAULT_DIFFICULTIES = [
    ("하양", "#e8e4da"),
    ("노랑", "#e5c04b"),
    ("초록", "#6f9a5c"),
    ("파랑", "#4f7bb0"),
    ("빨강", "#c04a38"),
    ("보라", "#7d5ba6"),
    ("회색", "#8a8a8a"),
    ("검정", "#3a3a3a"),
]


class Command(BaseCommand):
    help = "Kakao Local API로 전국 클라이밍장 수집 (KAKAO_REST_API_KEY 필요)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--bbox",
            help="수집 범위: minLng,minLat,maxLng,maxLat (기본: 남한 전역)",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="DB에 쓰지 않고 수집 결과만 출력"
        )

    def handle(self, *args, **options):
        env = environ.Env()
        api_key = env("KAKAO_REST_API_KEY", default="")
        if not api_key:
            raise CommandError(
                "KAKAO_REST_API_KEY가 없습니다. developers.kakao.com에서 "
                "REST API 키를 발급해 backend/.env에 추가하세요."
            )
        self.headers = {"Authorization": f"KakaoAK {api_key}"}
        self.request_count = 0

        bbox = KOREA_BBOX
        if options["bbox"]:
            bbox = tuple(float(v) for v in options["bbox"].split(","))

        places: dict[str, dict] = {}  # kakao place id → place
        for keyword in KEYWORDS:
            self._sweep(keyword, bbox, places, depth=0)

        rows = [p for p in places.values() if self._is_gym(p)]
        self.stdout.write(
            f"API 호출 {self.request_count}회, 장소 {len(places)}건 중 "
            f"클라이밍장 판정 {len(rows)}건"
        )

        if options["dry_run"]:
            for p in sorted(rows, key=lambda r: r["place_name"]):
                addr = p["road_address_name"] or p["address_name"]
                self.stdout.write(f"  {p['place_name']} — {addr}")
            return

        self._save(rows)

    # ---- 수집 -------------------------------------------------------------

    def _sweep(self, keyword, bbox, places, depth):
        """rect 검색. 45건이 꽉 차면 4등분해 재귀 (최대 깊이 8)."""
        min_lng, min_lat, max_lng, max_lat = bbox
        total, docs = self._search(keyword, bbox)
        if total >= PAGE_SIZE * MAX_PAGES and depth < 8:
            mid_lng = (min_lng + max_lng) / 2
            mid_lat = (min_lat + max_lat) / 2
            for sub in (
                (min_lng, min_lat, mid_lng, mid_lat),
                (mid_lng, min_lat, max_lng, mid_lat),
                (min_lng, mid_lat, mid_lng, max_lat),
                (mid_lng, mid_lat, max_lng, max_lat),
            ):
                self._sweep(keyword, sub, places, depth + 1)
            return
        for doc in docs:
            places[doc["id"]] = doc

    def _search(self, keyword, bbox):
        docs, total = [], 0
        for page in range(1, MAX_PAGES + 1):
            params = urllib.parse.urlencode(
                {
                    "query": keyword,
                    "rect": ",".join(str(v) for v in bbox),
                    "size": PAGE_SIZE,
                    "page": page,
                }
            )
            req = urllib.request.Request(f"{API_URL}?{params}", headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = jsonlib.load(resp)
            self.request_count += 1
            time.sleep(0.05)  # 쿼터 보호
            total = body["meta"]["total_count"]
            docs.extend(body["documents"])
            if body["meta"]["is_end"]:
                break
        return total, docs

    @staticmethod
    def _is_gym(place):
        name = place["place_name"]
        category = place.get("category_name", "")
        if any(token in name for token in EXCLUDE_TOKENS):
            return False
        # 카카오 카테고리(스포츠,레저 > 클라이밍)이거나 상호로 판정
        return "클라이밍" in category or any(
            token in name for token in ("클라이밍", "볼더", "암벽")
        )

    # ---- 적재 -------------------------------------------------------------

    @transaction.atomic
    def _save(self, rows):
        created = updated = 0
        for p in rows:
            gym, was_created = Gym.all_objects.update_or_create(
                name=p["place_name"],
                defaults={
                    "address": p["road_address_name"] or p["address_name"],
                    "location": Point(float(p["x"]), float(p["y"]), srid=4326),
                    "phone": p.get("phone", ""),
                    "website": p.get("place_url", ""),
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )
            created += was_created
            updated += not was_created
            # 난이도가 없는 암장에만 기본 8색 체계 부여 (기존 데이터 보존)
            if not gym.difficulties.exists():
                GymDifficulty.objects.bulk_create(
                    GymDifficulty(gym=gym, name=n, color=c, order=i)
                    for i, (n, c) in enumerate(DEFAULT_DIFFICULTIES)
                )
        self.stdout.write(self.style.SUCCESS(f"완료 — 신규 {created}, 갱신 {updated}"))
