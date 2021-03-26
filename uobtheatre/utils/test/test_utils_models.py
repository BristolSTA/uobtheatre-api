import pytest
from django.core.exceptions import ValidationError

from uobtheatre.bookings.models import Booking
from uobtheatre.payments.models import Payment
from uobtheatre.productions.models import Performance, Production
from uobtheatre.societies.models import Society
from uobtheatre.utils.models import validate_percentage
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


@pytest.mark.parametrize(
    "percentage, is_valid",
    [(-1, False), (0.1, True), (1, True), (0, True), (1.1, False), (10, False)],
)
def test_validate_percentage(percentage, is_valid):
    if not is_valid:
        with pytest.raises(ValidationError):
            validate_percentage(percentage)
    else:
        validate_percentage(percentage)
