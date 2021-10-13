# Generated by Django 3.2.7 on 2021-10-10 15:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_auto_20210929_1707"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[("PENDING", "In progress"), ("COMPLETED", "Completed")],
                default="COMPLETED",
                max_length=20,
            ),
        ),
    ]
