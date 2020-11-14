from django.contrib import admin

from uobtheatre.venues.models import SeatGroup, SeatType, Venue

admin.site.register(Venue)
admin.site.register(SeatType)
admin.site.register(SeatGroup)
