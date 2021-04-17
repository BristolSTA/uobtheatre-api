# Generated by Django 3.1.7 on 2021-04-17 19:30

import autoslug.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("images", "0001_initial"),
    ]

    operations = [
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField()),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        blank=True, editable=False, populate_from="name", unique=True
                    ),
                ),
                (
                    "banner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="society_banners",
                        to="images.image",
                    ),
                ),
                (
                    "logo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="society_logos",
                        to="images.image",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
