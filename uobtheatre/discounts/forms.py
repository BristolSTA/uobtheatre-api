from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement
from uobtheatre.utils.forms import MutationForm, ValidationError


class ConcessionTypeForm(MutationForm):
    class Meta:
        model = ConcessionType
        fields = (
            "name",
            "description",
        )


class DiscountForm(MutationForm):
    class Meta:
        model = Discount
        fields = (
            "percentage",
            "performances",
            "seat_group",
        )

    def clean_performances(self):
        performances = self.cleaned_data["performances"]

        if not performances:
            raise ValidationError("Please select at least one performance.")

        return performances


class DiscountRequirementForm(MutationForm):
    class Meta:
        model = DiscountRequirement
        fields = (
            "number",
            "discount",
            "concession_type",
        )
