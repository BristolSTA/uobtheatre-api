# Generated by Django 3.2.9 on 2021-11-28 21:08

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("productions", "0010_auto_20211124_2227"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="production",
            options={
                "ordering": ["id"],
                "permissions": (
                    ("boxoffice", "Can use boxoffice for production"),
                    ("sales", "Can view sales for production"),
                    ("force_change_production", "Can edit production once live"),
                    (
                        "approve_production",
                        "Can approve production pending publication",
                    ),
                ),
            },
        ),
    ]
