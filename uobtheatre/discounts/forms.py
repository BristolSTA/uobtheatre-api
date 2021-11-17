from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement
from uobtheatre.utils.forms import MutationForm


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


class DiscountRequirementForm(MutationForm):
    class Meta:
        model = DiscountRequirement
        fields = (
            "number",
            "discount",
            "concession_type",
        )
