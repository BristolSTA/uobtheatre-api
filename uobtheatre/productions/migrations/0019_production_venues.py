# Generated by Django 3.2.12 on 2022-03-22 10:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("venues", "0004_alter_venue_internal_capacity"),
        ("productions", "0018_merge_20220113_1935"),
    ]

    operations = [
        migrations.AddField(
            model_name="production",
            name="venues",
            field=models.ManyToManyField(
                editable=False, through="productions.Performance", to="venues.Venue"
            ),
        ),
    ]
