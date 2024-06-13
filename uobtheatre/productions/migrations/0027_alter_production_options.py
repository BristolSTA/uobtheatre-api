# give users with change_production permission the apply_booking_discount permission
# god save us all this might break everything

from django.db import migrations
from django.db import migrations, models


def add_apply_booking_discount(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    apply_booking_discount = Permission.objects.get(codename='apply_booking_discount')
    change_production = Permission.objects.get(codename='change_production')
    for group in Group.objects.filter(permissions=change_production):
        group.permissions.add(apply_booking_discount)

class Migration(migrations.Migration):

    dependencies = [
        ('productions', '0026_auto_20210224_1911'),
    ]

    operations = [
        migrations.AddField(
            model_name="production",
            name="apply_booking_discount",
            field=models.BooleanField(blank=False, null=False),
        ),
        migrations.RunPython(add_apply_booking_discount),
    ]
