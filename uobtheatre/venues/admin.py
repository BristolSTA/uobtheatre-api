from django.contrib import admin
from uobtheatre.venues.models import Venue, SeatType, SeatGroup

admin.site.register(Venue)
admin.site.register(SeatType)
admin.site.register(SeatGroup)
