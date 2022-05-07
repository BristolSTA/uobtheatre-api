from uobtheatre.bookings.models import Booking
from uobtheatre.utils.forms import MutationForm


class BookingForm(MutationForm):
    class Meta:
        model = Booking
        fields = (
            "status",
            "user",
            "performance",
            "tickets",
            "admin_discount_percentage",
            "assessibility_info",
        )
