from django.contrib import admin

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
    readonly_fields = ("subtotal", "total")
    list_display = ("reference",)
