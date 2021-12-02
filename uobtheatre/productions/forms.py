from uobtheatre.productions.models import Performance, PerformanceSeatGroup, Production
from uobtheatre.utils.forms import MutationForm
from django.core.exceptions import ValidationError


class ProductionForm(MutationForm):
    class Meta:
        model = Production
        fields = (
            "name",
            "subtitle",
            "society",
            "description",
            "cover_image",
            "poster_image",
            "featured_image",
            "age_rating",
            "facebook_event",
            "warnings",
        )


class PerformanceForm(MutationForm):
    def clean(self):
        cleaned_data = super().clean()
        doors_open = cleaned_data.get("doors_open")
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")

        if (doors_open and start) and (doors_open >= start):
            raise ValidationError(
                {"doors_open": "Doors open must be before the start time"}
            )

        if (start and end) and (start >= end):
            raise ValidationError(
                {"start": "The start time must be before the end time"}
            )

    class Meta:
        model = Performance
        fields = (
            "venue",
            "doors_open",
            "start",
            "end",
            "description",
            "disabled",
            "capacity",
            "production",
        )


class PerformanceSeatGroupForm(MutationForm):
    class Meta:
        model = PerformanceSeatGroup
        fields = (
            "seat_group",
            "performance",
            "price",
            "capacity",
        )
