from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_userprofile"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={"default_manager_name": "objects"},
        ),
    ]
