# Generated by Django 3.1.5 on 2021-01-29 09:27

import autoslug.fields
import django.db.models.deletion
from django.db import migrations, models

import uobtheatre.utils.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("venues", "0001_initial"),
        ("societies", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CrewRole",
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
                (
                    "department",
                    models.CharField(
                        choices=[
                            ("lighting", "Lighting"),
                            ("sound", "Sound"),
                            ("av", "AV"),
                            ("stage_management", "Stage Management"),
                            ("pryo", "Pyrotechnics"),
                            ("set", "Set"),
                            ("misc", "Miscellaneous"),
                        ],
                        default="misc",
                        max_length=20,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Performance",
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
                ("doors_open", models.DateTimeField(null=True)),
                ("start", models.DateTimeField(null=True)),
                ("end", models.DateTimeField(null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("extra_information", models.TextField(blank=True, null=True)),
                ("disabled", models.BooleanField(default=True)),
                ("capacity", models.IntegerField(blank=True, null=True)),
            ],
            options={
                "ordering": ["id"],
            },
            bases=(models.Model, uobtheatre.utils.models.TimeStampedMixin),
        ),
        migrations.CreateModel(
            name="Production",
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
                ("subtitle", models.CharField(max_length=255, null=True)),
                ("description", models.TextField(null=True)),
                ("poster_image", models.ImageField(null=True, upload_to="")),
                ("featured_image", models.ImageField(null=True, upload_to="")),
                ("cover_image", models.ImageField(null=True, upload_to="")),
                ("age_rating", models.SmallIntegerField(null=True)),
                ("facebook_event", models.CharField(max_length=255, null=True)),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        blank=True, editable=False, populate_from="name", unique=True
                    ),
                ),
                (
                    "society",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="productions",
                        to="societies.society",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
            bases=(models.Model, uobtheatre.utils.models.TimeStampedMixin),
        ),
        migrations.CreateModel(
            name="Warning",
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
                ("warning", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="ProductionTeamMember",
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
                ("role", models.CharField(max_length=255, null=True)),
                (
                    "production",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="production_team",
                        to="productions.production",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddField(
            model_name="production",
            name="warnings",
            field=models.ManyToManyField(to="productions.Warning"),
        ),
        migrations.CreateModel(
            name="PerformanceSeatGroup",
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
                ("capacity", models.SmallIntegerField(blank=True)),
                (
                    "performance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="performance_seat_groups",
                        to="productions.performance",
                    ),
                ),
                (
                    "seat_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        to="venues.seatgroup",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="performance",
            name="production",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="performances",
                to="productions.production",
            ),
        ),
        migrations.AddField(
            model_name="performance",
            name="seat_groups",
            field=models.ManyToManyField(
                through="productions.PerformanceSeatGroup", to="venues.SeatGroup"
            ),
        ),
        migrations.AddField(
            model_name="performance",
            name="venue",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="performances",
                to="venues.venue",
            ),
        ),
        migrations.CreateModel(
            name="CrewMember",
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
                (
                    "production",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crew",
                        to="productions.production",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="crew_members",
                        to="productions.crewrole",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="CastMember",
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
                (
                    "profile_picture",
                    models.ImageField(blank=True, null=True, upload_to=""),
                ),
                ("role", models.CharField(max_length=255, null=True)),
                (
                    "production",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cast",
                        to="productions.production",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
