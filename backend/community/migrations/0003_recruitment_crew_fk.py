# crews 앱 도입 — Recruitment.crew_id(정수 자리표시자) 를 crews.Crew FK 로 전환.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("community", "0002_recruitment_chat_room_fk"),
        ("crews", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="recruitment",
            name="crew_id",
        ),
        migrations.AddField(
            model_name="recruitment",
            name="crew",
            field=models.ForeignKey(
                blank=True,
                db_comment="크루 주최 모집일 때 크루 FK. NULL 이면 개인 모집",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="recruitments",
                to="crews.crew",
            ),
        ),
    ]
