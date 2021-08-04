from django.contrib import admin
from django.utils.html import format_html

from uobtheatre.bookings.models import Booking, MiscCost, Ticket

admin.site.register(MiscCost)


class SeatBookingInline(admin.StackedInline):
    model = Ticket
    extra = 1


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Admin for Booking model.

    Extends admin to include:
        - inline Tickets
        - price and discounted_price in list view
    """

    inlines = [SeatBookingInline]
    list_display = ("reference", "view_price", "view_price_with_discount")

    def view_price(self, booking):
        return format_html("<p> {} </p>", booking.get_price())

    def view_price_with_discount(self, booking):
        return format_html("<p> {} </p>", booking.subtotal())

    view_price.short_description = "Price"  # type: ignore

    view_price_with_discount.short_description = "Discounted Price"  # type: ignore
