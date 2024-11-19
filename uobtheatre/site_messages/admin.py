from django.contrib import admin

from uobtheatre.site_messages.models import Message


class MessageAdmin(admin.ModelAdmin):
    """Admin for Message model."""

    list_display = (
        "message",
        "active",
        "display_start",
        "event_start",
        "event_end",
        "type",
        "creator",
    )
    list_filter = ("active", "type")
    search_fields = ("message", "creator__email")
    date_hierarchy = "display_start"


admin.site.register(Message, MessageAdmin)
