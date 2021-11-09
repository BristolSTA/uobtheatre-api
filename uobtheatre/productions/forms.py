from uobtheatre.productions.models import Performance, Production
from uobtheatre.utils.forms import MutationForm


class ProductionForm(MutationForm):
    class Meta:
        model = Production
        fields = (
            "name",
            "subtitle",
            "description",
            "cover_image",
            "poster_image",
            "featured_image",
            "age_rating",
            "facebook_event",
            "warnings",
        )


class PerformanceForm(MutationForm):
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
