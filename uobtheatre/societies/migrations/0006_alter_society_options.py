# Generated by Django 3.2.8 on 2021-11-13 19:16

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("societies", "0005_auto_20210924_1401"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="society",
            options={
                "permissions": (
                    ("add_production", "Can add productions for this society"),
                )
            },
        ),
    ]
