# Generated by Django 3.1.3 on 2020-11-13 23:58

from django.db import migrations, models
import django.db.models.deletion
import uobtheatre.utils.models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('venues', '0001_initial'),
        ('productions', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking_reference', models.UUIDField(default=uuid.uuid4, editable=False)),
            ],
            bases=(models.Model, uobtheatre.utils.models.TimeStampedMixin),
        ),
        migrations.CreateModel(
            name='ConsessionType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='SeatBooking',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='seats', to='bookings.booking')),
                ('consession_type', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='seat_bookings', to='bookings.consessiontype')),
                ('performance', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='seat_bookings', to='productions.performance')),
                ('seat_group', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='seat_bookings', to='venues.seatgroup')),
            ],
        ),
    ]
