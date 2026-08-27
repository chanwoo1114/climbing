"""climbs 테스트 공용 헬퍼 — 암장/난이도/기록 생성."""

from django.contrib.gis.geos import Point

from climbs.models import ClimbLog
from gyms.models import Gym, GymDifficulty


def create_gym(name="테스트암장") -> Gym:
    return Gym.objects.create(
        name=name, address="서울", location=Point(127.0, 37.5, srid=4326)
    )


def create_difficulty(gym: Gym, name="초록", color="#5f7d4e", order=0) -> GymDifficulty:
    return GymDifficulty.objects.create(gym=gym, name=name, color=color, order=order)


def create_log(user, gym: Gym, **kwargs) -> ClimbLog:
    defaults = {"is_success": True, "attempts": 2, "memo": "기록", "is_shared": True}
    defaults.update(kwargs)
    return ClimbLog.objects.create(user=user, gym=gym, **defaults)
