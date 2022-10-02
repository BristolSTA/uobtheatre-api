# Generated by Django 3.2.15 on 2022-10-02 20:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0005_alter_booking_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='transferred_from',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='_transferred_to', to='bookings.booking'),
        ),
        migrations.AddField(
            model_name='misccost',
            name='type',
            field=models.CharField(choices=[('Booking', 'Applied to booking purchase')], default='Booking', max_length=24),
            preserve_default=False,
        ),
    ]
