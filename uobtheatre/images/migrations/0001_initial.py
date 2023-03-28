# Generated by Django 3.2.5 on 2021-07-18 12:38

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Image",
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
                ("file", models.ImageField(upload_to="")),
                ("alt_text", models.CharField(blank=True, max_length=50, null=True)),
            ],
        ),
    ]
