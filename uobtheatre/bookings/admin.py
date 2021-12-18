from admin_confirm import AdminConfirmMixin
from admin_confirm.admin import confirm_action
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
from uobtheatre.payments.models import Payment
from uobtheatre.utils.admin import ReadOnlyInlineMixin

admin.site.register(MiscCost)


class SeatBookingInline(admin.StackedInline):
    model = Ticket
    extra = 1


class PaymentsInline(GenericTabularInline, ReadOnlyInlineMixin):
    model = Payment
    ct_fk_field = "pay_object_id"
    ct_field = "pay_object_type"


@admin.register(Booking)
class BookingAdmin(AdminConfirmMixin, admin.ModelAdmin):
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

    @confirm_action
    @admin.action(description="Issue refund", permissions=["change"])
    def issue_refund(modeladmin, request, queryset):
        for booking in queryset:
            for payment in booking.payments.filter(
                type=Payment.PaymentType.PURCHASE
            ).all():
                payment.refund()

        modeladmin.message_user(
            request, f"{queryset.count()} objects have had refunds requested "
        )

    def get_performance_name(self, obj):
        return obj.performance.production.name

    get_performance_name.short_description = "production"  # type: ignore
