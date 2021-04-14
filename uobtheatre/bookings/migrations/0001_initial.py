# Generated by Django 3.1.7 on 2021-04-14 21:24

import django.db.models.deletion
from django.db import migrations, models

import uobtheatre.utils.models
import uobtheatre.utils.utils


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("productions", "0001_initial"),
        ("venues", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Booking",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reference",
                    models.CharField(
                        default=uobtheatre.utils.utils.create_short_uuid,
                        editable=False,
                        max_length=12,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("IN_PROGRESS", "In Progress"), ("PAID", "Paid")],
                        default="IN_PROGRESS",
                        max_length=20,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ConcessionType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Discount",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("percentage", models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name="DiscountRequirement",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("number", models.SmallIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name="MiscCost",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "percentage",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[uobtheatre.utils.models.validate_percentage],
                    ),
                ),
                ("value", models.FloatField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Ticket",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("checked_in", models.BooleanField(default=False)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tickets",
                        to="bookings.booking",
                    ),
                ),
                (
                    "concession_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="seat_bookings",
                        to="bookings.concessiontype",
                    ),
                ),
                (
                    "seat",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        to="venues.seat",
                    ),
                ),
                (
                    "seat_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="tickets",
                        to="venues.seatgroup",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="misccost",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(("percentage__isnull", True), ("value__isnull", False)),
                    models.Q(("percentage__isnull", False), ("value__isnull", True)),
                    _connector="OR",
                ),
                name="percentage_or_value_must_be_set_on_misc_cost",
            ),
        ),
        migrations.AddField(
            model_name="discountrequirement",
            name="concession_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="bookings.concessiontype",
            ),
        ),
        migrations.AddField(
            model_name="discountrequirement",
            name="discount",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="requirements",
                to="bookings.discount",
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="performances",
            field=models.ManyToManyField(
                blank=True, related_name="discounts", to="productions.Performance"
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="seat_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="venues.seatgroup",
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
    ]
