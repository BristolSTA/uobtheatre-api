# Generated by Django 3.1.7 on 2021-03-19 00:19

import autoslug.fields
from django.db import migrations, models


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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
            options={
                "abstract": False,
            },
        ),
    ]
