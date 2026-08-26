"""기존 계정 이메일을 소문자로 통일한다.

0006 에서 Lower(email) 유니크 제약을 추가하기 전에 실행되어야 한다.
대소문자만 다른 중복 계정이 이미 있으면 여기서 IntegrityError 로 멈춘다 —
조용히 한쪽을 지우는 것보다 사람이 확인해서 합치는 게 맞다.
"""

from django.db import migrations
from django.db.models.functions import Lower


def lowercase_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    # 히스토리 모델은 커스텀 매니저의 is_deleted 필터가 없으므로 탈퇴 계정도 포함된다.
    User.objects.exclude(email=Lower("email")).update(email=Lower("email"))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_alter_user_email_alter_user_nickname"),
    ]

    operations = [
        migrations.RunPython(lowercase_emails, migrations.RunPython.noop),
    ]
