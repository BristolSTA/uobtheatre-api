# Generated by Django 3.2.11 on 2022-01-26 23:25

from django.db import migrations


def convert_purcahse_to_payment(apps, _):
    Transaction = apps.get_model("payments", "Transaction")
    transactions = Transaction.objects.filter(type="PURCHASE")
    transactions.update(type="PAYMENT")


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0012_alter_transaction_provider_name"),
    ]

    operations = [
        migrations.RunPython(convert_purcahse_to_payment),
    ]
