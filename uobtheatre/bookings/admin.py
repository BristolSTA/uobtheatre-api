from django.contrib import admin
from django.utils.html import format_html

from uobtheatre.bookings.models import (
    Booking,
    ConcessionType,
    Discount,
    DiscountRequirement,
    Ticket,
)
from uobtheatre.productions.models import (
    PerformanceSeatGroup,
)

admin.site.register(ConcessionType)


class DiscountRequirementInline(admin.StackedInline):
    model = DiscountRequirement
    extra = 1


class DiscountAdmin(admin.ModelAdmin):
    inlines = [DiscountRequirementInline]


admin.site.register(Discount, DiscountAdmin)


class SeatBookingInline(admin.StackedInline):
    model = Ticket
    extra = 1


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    inlines = [SeatBookingInline]
    list_display = ("booking_reference", "view_price", "view_price_with_discount")

    def view_price(self, booking):
        return format_html("<p> {} </p>", booking.get_price())

    def view_price_with_discount(self, booking):
        return format_html(
            "<p> {} </p>", booking.get_best_discount_combination_with_price()[1]
        )

    view_price.short_description = "Price"
    view_price_with_discount.short_description = "Discounted Price"
