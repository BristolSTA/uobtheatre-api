# Generated by Django 3.2.18 on 2024-07-20 23:16

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('active', models.BooleanField(default=True)),
                ('indefinite_override', models.BooleanField(default=False)),
                ('display_start', models.DateTimeField(null=True)),
                ('event_start', models.DateTimeField()),
                ('event_end', models.DateTimeField()),
                ('type', models.CharField(choices=[('MAINTENANCE', 'Maintenance'), ('INFORMATION', 'Information'), ('ALERT', 'Alert')], default='MAINTENANCE', max_length=11)),
                ('dismissal_policy', models.CharField(choices=[('DEFAULT', 'Dismissable (Default)'), ('SINGLE', 'Single-Session Only'), ('BANNED', 'Prevented')], default='DEFAULT', max_length=7)),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='created_site_messages', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
