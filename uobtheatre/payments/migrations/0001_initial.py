# Generated by Django 3.2.5 on 2021-07-15 21:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
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
                ("pay_object_id", models.PositiveIntegerField()),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("PURCHASE", "Purchase payment"),
                            ("REFUND", "Refund payment"),
                        ],
                        default="PURCHASE",
                        max_length=20,
                    ),
                ),
                (
                    "provider_payment_id",
                    models.CharField(blank=True, max_length=40, null=True),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("CASH", "Cash"),
                            ("SQUARE_ONLINE", "Square online"),
                            ("SQUARE_POS", "Square point of sale"),
                        ],
                        default="SQUARE_ONLINE",
                        max_length=20,
                    ),
                ),
                ("value", models.IntegerField()),
                ("currency", models.CharField(default="GBP", max_length=10)),
                ("card_brand", models.CharField(blank=True, max_length=20, null=True)),
                ("last_4", models.CharField(blank=True, max_length=4, null=True)),
                (
                    "pay_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            ("app_label", "bookings"), ("model", "paidbooking")
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
