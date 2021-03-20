# Generated by Django 3.1.7 on 2021-03-20 15:53

import autoslug.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("addresses", "0001_initial"),
        ("images", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Seat",
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
                ("row", models.CharField(blank=True, max_length=5, null=True)),
                ("number", models.CharField(blank=True, max_length=5, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Venue",
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
                ("name", models.CharField(max_length=255)),
                ("internal_capacity", models.SmallIntegerField()),
                ("description", models.TextField(null=True)),
                ("publicly_listed", models.BooleanField(default=True)),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        blank=True, editable=False, populate_from="name", unique=True
                    ),
                ),
                (
                    "address",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="addresses.address",
                    ),
                ),
                (
                    "image",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="venues",
                        to="images.image",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="SeatGroup",
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
                ("capacity", models.IntegerField(null=True)),
                ("is_internal", models.BooleanField(default=True)),
                (
                    "seats",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        to="venues.seat",
                    ),
                ),
                (
                    "venue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seat_groups",
                        to="venues.venue",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
