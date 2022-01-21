# Generated by Django 3.2.11 on 2022-01-21 11:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_celery_results", "0010_remove_duplicate_indices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taskresult",
            name="status",
            field=models.CharField(
                choices=[
                    ("FAILURE", "FAILURE"),
                    ("PENDING", "PENDING"),
                    ("RECEIVED", "RECEIVED"),
                    ("RETRY", "RETRY"),
                    ("REVOKED", "REVOKED"),
                    ("SKIPPED", "SKIPPED"),
                    ("STARTED", "STARTED"),
                    ("SUCCESS", "SUCCESS"),
                ],
                default="PENDING",
                help_text="Current state of the task being run",
                max_length=50,
                verbose_name="Task State",
            ),
        ),
    ]
