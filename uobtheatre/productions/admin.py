from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from uobtheatre.productions.models import (
    AudienceWarning,
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionTeamMember,
)


class ProductionAdmin(GuardedModelAdmin):
    pass


admin.site.register(Production, ProductionAdmin)
admin.site.register(Performance)
admin.site.register(AudienceWarning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
admin.site.register(ProductionTeamMember)
