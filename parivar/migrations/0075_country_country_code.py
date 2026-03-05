from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parivar", "0074_randombanner_samaj"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE parivar_country "
                        "ADD COLUMN IF NOT EXISTS country_code varchar(10);"
                    ),
                    reverse_sql=(
                        "ALTER TABLE parivar_country "
                        "DROP COLUMN IF EXISTS country_code;"
                    ),
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="country",
                    name="country_code",
                    field=models.CharField(blank=True, max_length=10, null=True),
                )
            ],
        ),
    ]
