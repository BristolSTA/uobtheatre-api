import graphene
from django.core.exceptions import ValidationError
from django.forms import Field
from graphene_django.forms.converter import convert_form_field

from uobtheatre.productions.models import (
    ContentWarning,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionContentWarning,
)
from uobtheatre.utils.forms import MutationForm
from uobtheatre.utils.schema import IdInputField


class ProductionWarning(graphene.InputObjectType):
    """Input for creating Tickets with mutations."""

    information = graphene.String()
    id = IdInputField(required=True)


class ProductionWarningListField(Field):
    pass


@convert_form_field.register(ProductionWarningListField)
def convert_form_field_to_string(field):
    return graphene.List(
        ProductionWarning,
        description=field.help_text,
        required=field.required,
    )


class ProductionForm(MutationForm):
    """Form for productions"""

    contentWarnings = ProductionWarningListField(required=False)

    def clean(self):
        """Validate form data on clean"""
        cleaned_data = super().clean()
        warnings = cleaned_data.get("contentWarnings") or []

        for warning in warnings:
            if not ContentWarning.objects.filter(pk=warning["id"]).exists():
                raise ValidationError(
                    {
                        "contentWarnings": f"A warning with ID {warning['id']} does not exist"
                    }
                )

    def _save_m2m(self):
        """Save the many-to-many relations"""
        super()._save_m2m()

        if (warnings := self.cleaned_data.get("contentWarnings")) is not None:
            ProductionContentWarning.objects.filter(production=self.instance).delete()

            ProductionContentWarning.objects.bulk_create(
                [
                    ProductionContentWarning(
                        production=self.instance,
                        warning_id=warning.id,
                        information=warning.information,
                    )
                    for warning in warnings
                ]
            )

    class Meta:
        model = Production
        fields = (
            "name",
            "slug",
            "subtitle",
            "society",
            "description",
            "cover_image",
            "poster_image",
            "featured_image",
            "age_rating",
            "facebook_event",
            "support_email",
        )


class PerformanceForm(MutationForm):
    """Form for performance mutations"""

    def clean(self):
        """Validate form data on clean"""
        cleaned_data = super().clean()
        doors_open = cleaned_data.get("doors_open")
        start = cleaned_data.get("start") or self.instance.start
        end = cleaned_data.get("end") or self.instance.end
        interval_duration_mins = cleaned_data.get("interval_duration_mins")

        if (doors_open and start) and (doors_open >= start):
            raise ValidationError(
                {"doors_open": "Doors open must be before the start time"}
            )

        if (start and end) and (start >= end):
            raise ValidationError(
                {"start": "The start time must be before the end time"}
            )

        if (
            interval_duration_mins
            and interval_duration_mins >= (end - start).total_seconds() / 60
        ):
            raise ValidationError(
                {
                    "interval_duration_mins": "The length of the interval must be less than the length of the performance"
                }
            )

    class Meta:
        model = Performance
        fields = (
            "venue",
            "doors_open",
            "start",
            "end",
            "interval_duration_mins",
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
