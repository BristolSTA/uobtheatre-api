# Generated by Django 3.2.18 on 2024-03-06 23:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("venues", "0004_alter_venue_internal_capacity"),
    ]

    operations = [
        migrations.AddField(
            model_name="venue",
            name="accessibility_info",
            field=models.TextField(blank=True, null=True),
        ),
    ]
