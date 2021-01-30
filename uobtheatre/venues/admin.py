from django.contrib import admin

from uobtheatre.venues.models import SeatGroup, Venue, VenueLayout

admin.site.register(SeatGroup)
admin.site.register(VenueLayout)


class SeatGroupInlinne(admin.StackedInline):
    model = SeatGroup
    extra = 1


class VenueLayoutInlinne(admin.StackedInline):
    model = VenueLayout
    extra = 1


class VenueAdmin(admin.ModelAdmin):
    inlines = [SeatGroupInlinne]


admin.site.register(Venue, VenueAdmin)
