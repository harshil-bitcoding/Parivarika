from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parivar", "0074_randombanner_samaj"),
    ]

    operations = [
        migrations.AddField(
            model_name="country",
            name="country_code",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]

