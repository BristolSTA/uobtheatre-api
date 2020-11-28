# Generated by Django 3.1.3 on 2020-11-28 21:05

import uuid

import django.db.models.deletion
from django.db import migrations, models

import uobtheatre.utils.models


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
                (
                    "booking_reference",
                    models.UUIDField(default=uuid.uuid4, editable=False),
                ),
                (
                    "performance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="bookings",
                        to="productions.performance",
                    ),
                ),
            ],
            bases=(models.Model, uobtheatre.utils.models.TimeStampedMixin),
        ),
        migrations.CreateModel(
            name="ConsessionType",
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
                ("discount", models.FloatField()),
                (
                    "performances",
                    models.ManyToManyField(
                        blank=True,
                        related_name="discounts",
                        to="productions.Performance",
                    ),
                ),
                (
                    "seat_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="venues.seatgroup",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SeatBooking",
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
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="seat_bookings",
                        to="bookings.booking",
                    ),
                ),
                (
                    "consession_type",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="seat_bookings",
                        to="bookings.consessiontype",
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
                        related_name="seat_bookings",
                        to="venues.seatgroup",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PerformanceSeating",
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
                ("price", models.IntegerField()),
                ("capacity", models.SmallIntegerField(blank=True, null=True)),
                (
                    "performance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="seating",
                        to="productions.performance",
                    ),
                ),
                ("seat_group", models.ManyToManyField(to="venues.SeatGroup")),
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
                (
                    "consession_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="bookings.consessiontype",
                    ),
                ),
                (
                    "discount",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discount_requirements",
                        to="bookings.discount",
                    ),
                ),
            ],
        ),
    ]
