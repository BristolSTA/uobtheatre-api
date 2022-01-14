from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from uobtheatre.societies.models import Society

admin.site.register(Society, GuardedModelAdmin)
