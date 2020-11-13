from django.contrib import admin
from uobtheatre.productions.models import (
    Production,
    Society,
    Performance,
    Warning,
    CrewMember,
    CastMember,
)

admin.site.register(Production)
admin.site.register(Society)
admin.site.register(Performance)
admin.site.register(Warning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
