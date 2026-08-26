"""이메일 인증 도입 이전에 만들어진 계정은 인증 완료로 간주한다.

0007 로 email_verified_at 이 생기면 기존 계정은 전부 NULL(미인증)이라
로그인이 막힌다. 이미 쓰고 있던 사람을 잠그지 않도록 가입 시각으로 채운다.
되돌릴 때(backwards)는 컬럼 자체가 0007 에서 사라지므로 할 일이 없다.
"""

from django.db import migrations
from django.db.models import F


def mark_existing_users_verified(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(email_verified_at__isnull=True).update(
        email_verified_at=F("created_at")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_user_email_verified_at"),
    ]

    operations = [
        migrations.RunPython(mark_existing_users_verified, migrations.RunPython.noop),
    ]
