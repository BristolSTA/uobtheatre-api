# Generated by Django 3.2.9 on 2021-12-31 12:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0006_alter_payment_provider_payment_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="provider",
            field=models.CharField(
                choices=[
                    ("CASH", "CASH"),
                    ("CARD", "CARD"),
                    ("SQUARE_POS", "SQUARE_POS"),
                    ("SQUARE_ONLINE", "SQUARE_ONLINE"),
                    ("SQUARE_REFUND", "SQUARE_REFUND"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "In progress"),
                    ("COMPLETED", "Completed"),
                    ("FAILED", "Failed"),
                ],
                default="COMPLETED",
                max_length=20,
            ),
        ),
    ]
