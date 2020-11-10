from django.contrib import admin
from uobtheatre.productions.models import Production, Society, Venue, Performance

admin.site.register(Production)
admin.site.register(Society)
admin.site.register(Venue)
admin.site.register(Performance)
