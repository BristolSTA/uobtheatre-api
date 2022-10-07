from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin, TabularInline
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from guardian.admin import GuardedModelAdmin

from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.productions.models import (
    CastMember,
    ContentWarning,
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
from uobtheatre.utils.forms import SendEmailForm
from uobtheatre.utils.lang import pluralize


class PerformancesInline(TabularInline, ReadOnlyInlineMixin):
    model = Performance


class ProductionAdmin(GuardedModelAdmin):
    inlines = [PerformancesInline]


@admin.register(Performance)
class PerformanceAdmin(DangerousAdminConfirmMixin, ModelAdmin):
    """Custom performance admin page for actions"""

    actions = ["issue_refunds", "email_users"]

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

    @admin.action(description="Email users", permissions=["change"])
    def email_users(self, _, queryset):
        """Action to issue refund for bookings in selected performances(s)"""
        return redirect(
            f"/admin/productions/performance/email/{','.join(map(str, queryset.values_list('pk', flat=True)))}/"
        )

    def get_urls(self):
        urls = super().get_urls()
        return [path("email/<str:ids>/", self.send_email_view)] + urls

    def send_email_view(self, request, ids):
        """
        View to send an email to users in a performances
        """
        ids = map(int, ids.split(","))
        performances = Performance.objects.filter(pk__in=ids)
        users = list(performances.booked_users())

        performances_text = ", ".join(map(str, performances))
        reason = f"You are receiving this email as you have booking(s) for at least one of the following performances: {performances_text}."

        form = SendEmailForm(
            request.POST if request.method == "POST" else None,
            initial={
                "user_reason": reason,
                "users": users,
            },
        )

        # Disabled user and user_reason fields as these are populdated
        # automatically
        form.fields["users"].disabled = True
        form.fields["user_reason"].disabled = True
        form.fields[
            "user_reason"
        ].help_text = "This will be generated automatically for each user, this is the example for the first user"

        if form.is_valid():
            form.submit()
            self.message_user(request, "Emails sent succesfully!")
            return redirect("/admin/productions/performance/")

        context = dict(
            # Include common variables for rendering the admin template.
            self.admin_site.each_context(request),
            form=form,
            emails=[user.email for user in users],
        )
        return TemplateResponse(request, "send_email_form.html", context)


admin.site.register(Production, ProductionAdmin)
admin.site.register(ContentWarning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
admin.site.register(ProductionTeamMember)
