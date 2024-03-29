# Generated by Django 3.2.5 on 2021-07-18 12:38

import autoslug.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("societies", "0001_initial"),
        ("images", "0001_initial"),
        ("venues", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AudienceWarning",
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
                ("description", models.CharField(max_length=255)),
            ],
        ),
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("subtitle", models.CharField(max_length=255, null=True)),
                ("description", models.TextField(null=True)),
                ("age_rating", models.SmallIntegerField(null=True)),
                ("facebook_event", models.CharField(max_length=255, null=True)),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        blank=True, editable=False, populate_from="name", unique=True
                    ),
                ),
                (
                    "cover_image",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="production_cover_images",
                        to="images.image",
                    ),
                ),
                (
                    "featured_image",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="production_featured_images",
                        to="images.image",
                    ),
                ),
                (
                    "poster_image",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="production_poster_images",
                        to="images.image",
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
                (
                    "warnings",
                    models.ManyToManyField(
                        blank=True, to="productions.AudienceWarning"
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
                "permissions": (
                    ("boxoffice", "Can use boxoffice for this show"),
                    ("create", "Can create a new production"),
                    ("edit", "Can edit existing production"),
                ),
            },
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
                ("role", models.CharField(max_length=255, null=True)),
                (
                    "production",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cast",
                        to="productions.production",
                    ),
                ),
                (
                    "profile_picture",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="cast_members",
                        to="images.image",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
