from uobtheatre.discounts.models import ConcessionType
from uobtheatre.utils.forms import MutationForm


class ConcessionTypeForm(MutationForm):
    class Meta:
        model = ConcessionType
        fields = (
            "name",
            "description",
        )
