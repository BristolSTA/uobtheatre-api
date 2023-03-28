# Generated by Django 3.2.5 on 2021-07-18 12:38

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bookings", "0001_initial"),
        ("productions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="creator",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="created_bookings",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="performance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="bookings",
                to="productions.performance",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bookings",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "IN_PROGRESS")),
                fields=("status", "performance"),
                name="one_in_progress_booking_per_user_per_performance",
            ),
        ),
    ]
