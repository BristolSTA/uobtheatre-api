# Generated by Django 3.2.15 on 2022-09-04 18:40

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("societies", "0006_alter_society_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payments", "0013_rename_purchase_type_on_transaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinancialTransfer",
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
                ("value", models.PositiveIntegerField()),
                (
                    "method",
                    models.CharField(
                        choices=[("INTERNAL", "Internal"), ("BACS", "BACS")],
                        max_length=20,
                    ),
                ),
                ("reason", models.TextField(null=True)),
                (
                    "society",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="societies.society",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "permissions": (("create_transfer", "Create a transfer entry"),),
            },
        ),
    ]