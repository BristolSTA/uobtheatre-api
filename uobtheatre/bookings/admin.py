from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.mail import mail_admins
from django.forms.models import BaseInlineFormSet
from django_celery_results.models import TaskResult
from django.utils.html import format_html
from nonrelated_inlines.admin import NonrelatedStackedInline

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
from uobtheatre.payments.emails import payable_refund_initiated_email
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.utils.admin import (
    DangerousAdminConfirmMixin,
    ReadOnlyInlineMixin,
    TaskResultInline,
    confirm_dangerous_action,
)

admin.site.register(MiscCost)


class SeatBookingInline(ReadOnlyInlineMixin, admin.StackedInline):
    model = Ticket


class TransactionInline(GenericTabularInline, ReadOnlyInlineMixin):
    model = Transaction
    ct_fk_field = "pay_object_id"
    ct_field = "pay_object_type"


class StatusFilter(SimpleListFilter):
    """A filter for to get refunded bookings"""

    title = "Status"
    parameter_name = "Status"

    def lookups(self, _, __):
        return (
            ("refunded", "Refunded"),
            ("locked", "Locked"),
        ) + tuple(Booking.Status.choices)

    def queryset(self, _, queryset):
        """
        Filter the status based on the lookup. First checks for refunded and
        locked, then handled the db statuses.
        """
        if self.value() == "refunded":
            return queryset.refunded()
        if self.value() == "locked":
            return queryset.locked()
        # If the query is a valid choice
        if self.value() in [choice[0] for choice in Booking.Status.choices]:
            return queryset.filter(status=self.value())
        return queryset


class BookingTaskStackedInline(ReadOnlyInlineMixin, NonrelatedStackedInline):
    model = TaskResult
    fields = [
        'id',
        "status",
    ]

    def get_form_queryset(self, obj):
        return obj.associated_tasks.all()

    def save_new_instance(self, parent, instance):
        raise NotImplementedError

@admin.register(Booking)
class BookingAdmin(DangerousAdminConfirmMixin, admin.ModelAdmin):
    """Admin for Booking model.

    Extends admin to include:
        - inline Tickets
        - price and discounted_price in list view
    """

    list_filter = (StatusFilter,)
    readonly_fields = ("subtotal", "total", "is_refunded", "is_locked")
    list_display = ("reference", "status", "get_performance_name")
    search_fields = [
        "reference",
        "performance__production__name",
        "user__email",
    ]
    actions = ["issue_refund"]
    inlines = [TransactionInline, SeatBookingInline, BookingTaskStackedInline]

    @confirm_dangerous_action
    @admin.action(description="Issue refund", permissions=["change"])
    def issue_refund(self, request, queryset):
        """Action to issue refund for selected booking(s)"""
        refunded_bookings = []
        for booking in queryset:
            try:
                booking.refund(authorizing_user=request.user, send_admin_email=False)
                refunded_bookings.append(booking)
            except CantBeRefundedException:
                self.message_user(
                    request,
                    f"One or more bookings could not be refunded ({booking})",
                    level=messages.ERROR,
                )
                break

        if num_refunded := len(refunded_bookings):
            self.message_user(
                request, f"{num_refunded} bookings have had refunds requested"
            )

            mail = payable_refund_initiated_email(request.user, refunded_bookings)
            mail_admins(
                "Booking Refunds Initiated",
                mail.to_plain_text(),
                html_message=mail.to_html(),
            )

    def get_performance_name(self, obj):
        return obj.performance.production.name

    get_performance_name.short_description = "production"  # type: ignore
