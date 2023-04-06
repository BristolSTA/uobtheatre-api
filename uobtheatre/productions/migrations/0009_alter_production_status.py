# Generated by Django 3.2.9 on 2021-12-30 11:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("productions", "0008_auto_20211202_1601"),
    ]

    operations = [
        migrations.AlterField(
            model_name="production",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("PENDING", "Pending"),
                    ("PUBLISHED", "Published"),
                    ("CANCELLED", "Cancelled"),
                    ("CLOSED", "Closed"),
                    ("COMPLETE", "Complete"),
                ],
                default="DRAFT",
                max_length=10,
            ),
        ),
    ]
