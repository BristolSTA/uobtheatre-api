from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
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

    inlines = [SeatBookingInline]
    list_filter = ("status",)
    readonly_fields = ("subtotal", "total")
    list_display = ("reference", "status", "get_performance_name")
    search_fields = [
        "reference",
        "performance__production__name",
        "user__email",
    ]
    actions = ["issue_refund"]
    inlines = [PaymentsInline]

    @confirm_dangerous_action
    @admin.action(description="Issue refund", permissions=["change"])
    def issue_refund(self, request, queryset):
        """Action to issue refund for selected booking(s)"""
        for booking in queryset:
            # Check if booking is paid
            if not booking.status == Booking.PayableStatus.PAID:
                self.message_user(
                    request,
                    f"One or more booking is not of status paid ({booking})",
                    level=messages.ERROR,
                )
                return

            for payment in booking.payments.filter(
                type=Payment.PaymentType.PURCHASE
            ).all():
                payment.refund()

        self.message_user(
            request, f"{queryset.count()} objects have had refunds requested "
        )

    def get_performance_name(self, obj):
        return obj.performance.production.name

    get_performance_name.short_description = "production"  # type: ignore
