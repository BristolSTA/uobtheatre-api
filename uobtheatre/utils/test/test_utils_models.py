import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.payments.models import Transaction
from uobtheatre.productions.models import Performance, Production
from uobtheatre.societies.models import Society
from uobtheatre.venues.models import Venue
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.users.models import User


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_type",
    [Booking, Venue, Society, Production, Performance, Transaction],
)
def test_timestamped_mixin(model_type):
    model = model_type()
    # create a class with the mixin
    assert hasattr(model, "created_at")
    assert hasattr(model, "updated_at")


@pytest.mark.django_db
def test_base_clone():
    user = UserFactory(email="abc@email.com")
    user_count = User.objects.count()

    user_2 = user.clone()

    # Assert user count not change, i.e. new model is not saved
    assert User.objects.count() == user_count

    # Assert attributes are copied
    assert user_2.email == "abc@email.com"

    # Assert pk is not
    assert user_2.pk is None
