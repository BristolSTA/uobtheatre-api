# Generated by Django 3.2.7 on 2021-09-23 10:01

import django_tiptap.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("societies", "0002_society_members"),
    ]

    operations = [
        migrations.AlterField(
            model_name="society",
            name="description",
            field=django_tiptap.fields.TipTapTextField(),
        ),
    ]
