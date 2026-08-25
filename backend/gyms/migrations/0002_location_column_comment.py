"""PostGIS geometry 컬럼 코멘트 보정.

CREATE TABLE 시점에는 db_comment 가 반영되지만, 이후 AlterField 로 geography
컬럼을 수정하면 GeoDjango 가 COMMENT 를 누락한다. 재적용해 두어 스키마를
다시 만들지 않아도 코멘트가 유지되게 한다.
"""

from django.db import migrations

COMMENT = "위치 좌표 (WGS84 Point). 거리순 정렬·뷰포트(bbox) 검색에 사용"


class Migration(migrations.Migration):
    dependencies = [("gyms", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql=[("COMMENT ON COLUMN public.gyms_gym.location IS %s", [COMMENT])],
            reverse_sql=["COMMENT ON COLUMN public.gyms_gym.location IS NULL"],
        )
    ]
