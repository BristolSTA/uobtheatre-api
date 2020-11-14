from django.contrib import admin

from uobtheatre.bookings.models import Booking, ConsessionType, SeatBooking

admin.site.register(ConsessionType)
admin.site.register(SeatBooking)
admin.site.register(Booking)
