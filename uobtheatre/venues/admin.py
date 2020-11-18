from django.contrib import admin

from uobtheatre.venues.models import SeatGroup, Venue

admin.site.register(SeatGroup)


class SeatGroupInlinne(admin.StackedInline):
    model = SeatGroup
    extra = 1


class VenueAdmin(admin.ModelAdmin):
    inlines = [SeatGroupInlinne]


admin.site.register(Venue, VenueAdmin)
