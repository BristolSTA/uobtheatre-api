# Generated by Django 3.1.3 on 2020-11-11 23:42

from django.db import migrations, models
import django.db.models.deletion
import uobtheatre.utils.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
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
            ],
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
            ],
        ),
        migrations.CreateModel(
            name="Society",
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
            bases=(
                models.Model,
                uobtheatre.utils.models.SoftDeletionMixin,
                uobtheatre.utils.models.TimeStampedMixin,
            ),
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
                ("name", models.CharField(max_length=255)),
            ],
            bases=(
                models.Model,
                uobtheatre.utils.models.SoftDeletionMixin,
                uobtheatre.utils.models.TimeStampedMixin,
            ),
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
                ("age_rating", models.SmallIntegerField(null=True)),
                ("facebook_event", models.CharField(max_length=255, null=True)),
                (
                    "cast",
                    models.ManyToManyField(blank=True, to="productions.CastMember"),
                ),
                (
                    "crew",
                    models.ManyToManyField(blank=True, to="productions.CrewMember"),
                ),
                (
                    "society",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="productions.society",
                    ),
                ),
                ("warnings", models.ManyToManyField(to="productions.Warning")),
            ],
            bases=(
                models.Model,
                uobtheatre.utils.models.SoftDeletionMixin,
                uobtheatre.utils.models.TimeStampedMixin,
            ),
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
                ("start", models.DateTimeField(null=True)),
                ("end", models.DateTimeField(null=True)),
                ("extra_information", models.TextField(blank=True, null=True)),
                (
                    "production",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="performances",
                        to="productions.production",
                    ),
                ),
                (
                    "venue",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="productions.venue",
                    ),
                ),
            ],
            bases=(
                models.Model,
                uobtheatre.utils.models.SoftDeletionMixin,
                uobtheatre.utils.models.TimeStampedMixin,
            ),
        ),
        migrations.AddField(
            model_name="crewmember",
            name="role",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="productions.crewrole",
            ),
        ),
    ]
