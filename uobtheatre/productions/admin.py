from django.contrib import admin

from uobtheatre.productions.models import (
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    Production,
    Society,
    Warning,
    PerformanceSeatGroup,
)

admin.site.register(Production)
admin.site.register(Society)
admin.site.register(Performance)
admin.site.register(Warning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
