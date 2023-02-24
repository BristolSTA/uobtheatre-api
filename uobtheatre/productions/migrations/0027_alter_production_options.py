# Generated by Django 3.2.16 on 2023-02-24 19:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('productions', '0026_auto_20221210_2056'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='production',
            options={'ordering': ['id'], 'permissions': (('boxoffice', 'Can use boxoffice for production'), ('sales', 'Can view sales for production'), ('force_change_production', 'Can edit production once live'), ('view_bookings', 'Can inspect bookings and users for this production'), ('approve_production', 'Can approve production pending publication'), ('apply_booking_discount', 'Can create comps for a production'))},
        ),
    ]
