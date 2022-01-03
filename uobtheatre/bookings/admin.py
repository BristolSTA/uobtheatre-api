from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.mail import mail_admins

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
from uobtheatre.mail.composer import MailComposer
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Payment
from uobtheatre.utils.admin import (
    DangerousAdminConfirmMixin,
    ReadOnlyInlineMixin,
    confirm_dangerous_action,
)

admin.site.register(MiscCost)


class SeatBookingInline(admin.StackedInline):
    model = Ticket
    extra = 1


class PaymentsInline(GenericTabularInline, ReadOnlyInlineMixin):
    model = Payment
    ct_fk_field = "pay_object_id"
    ct_field = "pay_object_type"


@admin.register(Booking)
class BookingAdmin(DangerousAdminConfirmMixin, admin.ModelAdmin):
    """Admin for Booking model.

    Extends admin to include:
        - inline Tickets
        - price and discounted_price in list view
    """

    list_filter = ("status",)
    readonly_fields = ("subtotal", "total")
    list_display = ("reference", "status", "get_performance_name")
    search_fields = [
        "reference",
        "performance__production__name",
        "user__email",
    ]
    actions = ["issue_refund"]
    inlines = [PaymentsInline, SeatBookingInline]

    @confirm_dangerous_action
    @admin.action(description="Issue refund", permissions=["change"])
    def issue_refund(self, request, queryset):
        """Action to issue refund for selected booking(s)"""
        for booking in queryset:
            # Check if booking is paid
            try:
                booking.refund()
            except CantBeRefundedException:
                self.message_user(
                    request,
                    "One or more bookings cannot be refunded",
                    level=messages.ERROR,
                )
                return

        self.message_user(
            request, f"{queryset.count()} bookings have had refunds requested "
        )
        mail = (
            MailComposer()
            .line("Refunds have been initiated for the following bookings:")
            .line(", ".join(f"{booking} ({booking.id})" for booking in queryset))
            .line(
                f"This action was requested by {request.user.full_name} ({request.user.email})"
            )
        )
        mail_admins(
            "Booking Refunds Initiated",
            mail.to_plain_text(),
            html_message=mail.to_html(),
        )

    def get_performance_name(self, obj):
        return obj.performance.production.name

    get_performance_name.short_description = "production"  # type: ignore
