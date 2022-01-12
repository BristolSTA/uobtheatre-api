from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.mail import mail_admins

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
from uobtheatre.payments.emails import payable_refund_initiated_email
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.utils.admin import (
    DangerousAdminConfirmMixin,
    ReadOnlyInlineMixin,
    confirm_dangerous_action,
)

admin.site.register(MiscCost)


class SeatBookingInline(admin.StackedInline):
    model = Ticket
    extra = 1


class TransactionInline(GenericTabularInline, ReadOnlyInlineMixin):
    model = Transaction
    ct_fk_field = "pay_object_id"
    ct_field = "pay_object_type"


class RefundedFilter(SimpleListFilter):
    """A filter for to get refunded bookings"""

    title = "refunded"
    parameter_name = "refunded"

    def lookups(self, _, __):
        return (("yes", "Yes"),)

    def queryset(self, _, queryset):
        if self.value() == "yes":
            return queryset.refunded()
        return queryset


@admin.register(Booking)
class BookingAdmin(DangerousAdminConfirmMixin, admin.ModelAdmin):
    """Admin for Booking model.

    Extends admin to include:
        - inline Tickets
        - price and discounted_price in list view
    """

    list_filter = ("status", RefundedFilter)
    readonly_fields = ("subtotal", "total", "is_refunded", "is_locked")
    list_display = ("reference", "status", "get_performance_name")
    search_fields = [
        "reference",
        "performance__production__name",
        "user__email",
    ]
    actions = ["issue_refund"]
    inlines = [TransactionInline, SeatBookingInline]

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
