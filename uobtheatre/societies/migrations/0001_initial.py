# Generated by Django 3.1.7 on 2021-03-11 20:15

import autoslug.fields
from django.db import migrations, models

import uobtheatre.utils.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

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
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("logo", models.ImageField(upload_to="")),
                ("banner", models.ImageField(upload_to="")),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        blank=True, editable=False, populate_from="name", unique=True
                    ),
                ),
            ],
            bases=(models.Model, uobtheatre.utils.models.TimeStampedMixin),
        ),
    ]
