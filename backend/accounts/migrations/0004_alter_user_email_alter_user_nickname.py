from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                db_comment="로그인 ID로 쓰는 이메일",
                max_length=254,
                unique=True,
                verbose_name="이메일",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="nickname",
            field=models.CharField(
                db_comment="표시 이름 (중복 불가)",
                max_length=30,
                unique=True,
                verbose_name="닉네임",
            ),
        ),
    ]
