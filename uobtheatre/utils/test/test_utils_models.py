import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.payments.models import Payment
from uobtheatre.productions.models import Performance, Production
from uobtheatre.societies.models import Society
from uobtheatre.venues.models import Venue


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_type",
    [Booking, Venue, Society, Production, Performance, Payment],
)
def test_timestamped_mixin(model_type):
    model = model_type()
    # create a class with the mixin
    assert hasattr(model, "created_at")
    assert hasattr(model, "updated_at")
