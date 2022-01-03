from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin, TabularInline
from django.core.mail import mail_admins
from guardian.admin import GuardedModelAdmin

from uobtheatre.mail.composer import MailComposer
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
        for performance in queryset:
            try:
                performance.refund_bookings()
            except CantBeRefundedException as exception:
                self.message_user(
                    request,
                    exception.message,
                    level=messages.ERROR,
                )
                return

        self.message_user(
            request,
            "Eligable bookings on the performance have had refunds requested ",
        )
        mail = (
            MailComposer()
            .line("Refunds have been initiated for the following productions:")
            .line(
                ", ".join(f"{production} ({production.id})" for production in queryset)
            )
            .line(
                f"This action was requested by {request.user.full_name} ({request.user.email})"
            )
        )
        mail_admins(
            "Production Refunds Initiated",
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
