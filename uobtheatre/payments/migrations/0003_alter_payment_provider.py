# Generated by Django 3.2.6 on 2021-08-19 20:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_alter_payment_provider"),
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
                ],
                max_length=20,
            ),
        ),
    ]
