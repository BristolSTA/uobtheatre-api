from typing import Iterable

from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin, TabularInline
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
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
from uobtheatre.users.models import User
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

    @staticmethod
    def _generate_user_reason(performances: Iterable["Performance"], user: User):
        """
        Generate string reason for why the user is being sent the email
        """
        user_bookings = user.bookings.filter(performance__in=performances)
        user_performances = Performance.objects.filter(
            bookings__in=user_bookings
        ).distinct()

        if len(user_performances) == 1:
            return f"You are reciving this email as you have {pluralize('a booking', user_bookings, 'bookings')} for {str(user_performances.first())}."

        performances_text = ", ".join(map(str, user_performances))
        return f"You are reciving this email as you have bookings for the following performances: {performances_text}."

    def send_email_view(self, request, ids):
        """
        View to send an email to users in a performances
        """
        ids = map(int, ids.split(","))
        performances = Performance.objects.filter(pk__in=ids)
        users = list(performances.booked_users())

        form = SendEmailForm(
            request.POST if request.method == "POST" else None,
            initial={
                "user_reason": self._generate_user_reason(performances, users[0])
                if len(users) > 0
                else "",
                "users": users,
            },
        )
        form.fields[
            "user_reason"
        ].help_text = "This will be generated automatically for each user, this is the example for the first user"

        if form.is_valid():
            form.user_reason_generator = lambda user: self._generate_user_reason(
                performances, user
            )
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
admin.site.register(AudienceWarning)
admin.site.register(CrewMember)
admin.site.register(CastMember)
admin.site.register(CrewRole)
admin.site.register(PerformanceSeatGroup)
admin.site.register(ProductionTeamMember)
