from django.contrib import admin
from uobtheatre.bookings.models import ConsessionType, SeatBooking, Booking

admin.site.register(ConsessionType)
admin.site.register(SeatBooking)
admin.site.register(Booking)
