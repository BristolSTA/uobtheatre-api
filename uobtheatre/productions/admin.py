from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin, TabularInline
from django.core.mail import mail_admins
from guardian.admin import GuardedModelAdmin

from uobtheatre.payments.emails import payable_refund_initiated_email
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
        refunded_performances = []
        for performance in queryset:
            try:
                performance.refund_bookings(
                    authorizing_user=request.user, send_admin_email=False
                )
                refunded_performances.append(performance)
            except CantBeRefundedException as exception:
                self.message_user(
                    request,
                    exception.message,
                    level=messages.ERROR,
                )

        if len(refunded_performances) > 0:
            self.message_user(
                request,
                "Eligable bookings on the performance(s) have had refunds requested ",
            )
            mail = payable_refund_initiated_email(request.user, refunded_performances)
            mail_admins(
                "Performance Refunds Initiated",
                mail.to_plain_text(),
                html_message=mail.to_html(),
            )


admin.site.register(Production, ProductionAdmin)
admin.site.register(Society)
admin.site.register(AudienceWarning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
admin.site.register(ProductionTeamMember)
