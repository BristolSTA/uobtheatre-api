# Generated by Django 3.2.15 on 2022-09-26 17:06

from datetime import datetime

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def ticket_check_in_to_datetime(apps, _):
    ticket_model = apps.get_model("bookings", "ticket")

    ticket_model.objects.filter(checked_in=True).update(
        checked_in_at=datetime(
            year=2000, month=1, day=1, tzinfo=timezone.get_current_timezone()
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bookings", "0005_alter_booking_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="checked_in_at",
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="checked_in_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="tickets_checked_in_by_user",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(ticket_check_in_to_datetime),
        migrations.RemoveField(
            model_name="ticket",
            name="checked_in",
        ),
    ]
