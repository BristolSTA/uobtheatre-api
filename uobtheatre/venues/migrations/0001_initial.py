# Generated by Django 3.1.4 on 2020-12-31 18:07

import autoslug.fields
from django.db import migrations, models
import django.db.models.deletion
import uobtheatre.utils.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('addresses', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Seat',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row', models.CharField(blank=True, max_length=5, null=True)),
                ('number', models.CharField(blank=True, max_length=5, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Venue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('internal_capacity', models.SmallIntegerField()),
                ('description', models.TextField(null=True)),
                ('image', models.ImageField(null=True, upload_to='')),
                ('publicly_listed', models.BooleanField(default=True)),
                ('slug', autoslug.fields.AutoSlugField(blank=True, editable=False, populate_from='name', unique=True)),
                ('address', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='addresses.address')),
            ],
            bases=(models.Model, uobtheatre.utils.models.TimeStampedMixin),
        ),
        migrations.CreateModel(
            name='SeatGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('capacity', models.IntegerField(null=True)),
                ('is_internal', models.BooleanField(default=True)),
                ('seats', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, to='venues.seat')),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seat_groups', to='venues.venue')),
            ],
        ),
    ]
