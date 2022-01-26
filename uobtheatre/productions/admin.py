from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin, TabularInline
from guardian.admin import GuardedModelAdmin

from uobtheatre.payments.exceptions import CantBeRefundedException
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
from uobtheatre.utils.admin import (
    DangerousAdminConfirmMixin,
    ReadOnlyInlineMixin,
    confirm_dangerous_action,
)
from uobtheatre.utils.lang import pluralize


class PerformancesInline(TabularInline, ReadOnlyInlineMixin):
    model = Performance


class ProductionAdmin(GuardedModelAdmin):
    inlines = [PerformancesInline]


@admin.register(Performance)
class PerformanceAdmin(DangerousAdminConfirmMixin, ModelAdmin):
    """Custom performance admin page for actions"""

    actions = ["issue_refunds"]

    @confirm_dangerous_action
    @admin.action(description="Issue refunds", permissions=["change"])
    def issue_refunds(self, request, queryset):
        """Action to issue refund for bookings in selected performances(s)"""
        successful_count = 0
        for performance in queryset:
            try:
                performance.refund_bookings(authorizing_user=request.user)
                successful_count += 1
            except CantBeRefundedException as exception:
                self.message_user(
                    request,
                    exception.message,
                    level=messages.ERROR,
                )
        self.message_user(
            request,
            f"Requested refunds for {successful_count} {pluralize('performance', successful_count)}.",
        )


admin.site.register(Production, ProductionAdmin)
admin.site.register(AudienceWarning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
admin.site.register(ProductionTeamMember)
