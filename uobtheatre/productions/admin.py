from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin, TabularInline
from django.core.mail import mail_admins
from guardian.admin import GuardedModelAdmin

from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.productions.emails import performances_refunded_email
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
        refunded_bookings = []
        failed_bookings = []
        skipped_bookings = []
        performances = []
        for performance in queryset:
            try:
                (
                    performance_refunded_bookings,
                    performance_failed_bookings,
                    performance_skipped_bookings,
                ) = performance.refund_bookings(
                    authorizing_user=request.user, send_admin_email=False
                )
                refunded_bookings += performance_refunded_bookings
                failed_bookings += performance_failed_bookings
                skipped_bookings += performance_skipped_bookings
                performances.append(performance)
            except CantBeRefundedException as exception:
                self.message_user(
                    request,
                    exception.message,
                    level=messages.ERROR,
                )

        if len(performances) > 0:
            self.message_user(
                request,
                "Eligable bookings on the performance(s) have had refunds requested (Refunded: %s, Skipped: %s, Failed: %s)"
                % (len(refunded_bookings), len(skipped_bookings), len(failed_bookings)),
            )
            mail = performances_refunded_email(
                request.user,
                performances,
                refunded_bookings,
                skipped_bookings,
                failed_bookings,
            )
            mail_admins(
                "Performance Refunds Initiated",
                mail.to_plain_text(),
                html_message=mail.to_html(),
            )


admin.site.register(Production, ProductionAdmin)
admin.site.register(AudienceWarning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
admin.site.register(ProductionTeamMember)
