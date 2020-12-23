import pytest
from django.db import models

from uobtheatre.utils.models import TimeStampedMixin
from uobtheatre.bookings.models import Booking
from uobtheatre.venues.models import Venue
from uobtheatre.societies.models import Society
from uobtheatre.productions.models import Production, Performance


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_type",
    [Booking, Venue, Society, Production, Performance],
)
def test_timestamped_mixin(model_type):
    model = model_type()
    # create a class with the mixin
    assert hasattr(model, "created_at")
    assert hasattr(model, "updated_at")
