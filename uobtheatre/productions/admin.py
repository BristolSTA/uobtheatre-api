from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin, TabularInline
from guardian.admin import GuardedModelAdmin

from uobtheatre.payments.models import Payment
from uobtheatre.payments.payables import Payable
from uobtheatre.productions.models import (
    AudienceWarning,
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionTeamMember,
    Society,
)
from uobtheatre.utils.admin import (
    DangerousAdminConfirmMixin,
    ReadOnlyInlineMixin,
    confirm_dangerous_action,
)


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
        for performance in queryset:
            # Check if performance is marked as cancelled
            if not performance.disabled:
                self.message_user(
                    request,
                    f"One or more performances are not set to disabled ({performance})",
                    level=messages.ERROR,
                )
                return

            for booking in performance.bookings.filter(
                status=Payable.PayableStatus.PAID
            ):
                for payment in booking.payments.filter(
                    type=Payment.PaymentType.PURCHASE
                ).all():
                    payment.refund()

        self.message_user(
            request,
            f"{queryset.count()} performances have had elgiable bookings refunds requested ",
        )


admin.site.register(Production, ProductionAdmin)
admin.site.register(Society)
admin.site.register(AudienceWarning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
admin.site.register(ProductionTeamMember)
