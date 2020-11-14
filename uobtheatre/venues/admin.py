from django.contrib import admin

from uobtheatre.venues.models import SeatGroup, SeatType, Venue

admin.site.register(SeatType)
admin.site.register(SeatGroup)


class SeatGroupInlinne(admin.StackedInline):
    model = SeatGroup
    extra = 1


class VenueAdmin(admin.ModelAdmin):
    inlines = [SeatGroupInlinne]


admin.site.register(Venue, VenueAdmin)
