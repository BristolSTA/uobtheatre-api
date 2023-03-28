# Generated by Django 3.2.13 on 2022-06-12 13:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("productions", "0020_performance_interval_length_minutes"),
    ]

    operations = [
        migrations.RenameModel("AudienceWarning", "ContentWarning"),
        migrations.RenameField(
            model_name="contentwarning",
            old_name="description",
            new_name="short_description",
        ),
        migrations.AddField(
            model_name="contentwarning",
            name="long_description",
            field=models.TextField(null=True),
        ),
    ]
