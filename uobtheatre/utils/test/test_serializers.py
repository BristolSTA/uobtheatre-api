import uuid
import pytest
from uobtheatre.utils.serializers import UserIdSerializer
from uobtheatre.bookings.serializers import BookingSerialiser


def test_user_id_serializer():
    id = uuid.UUID("38400000-8cf0-11bd-b23e-10b96e4ef00d")
    serialized_user_id = UserIdSerializer()
    assert (
        serialized_user_id.to_representation(id)
        == "38400000-8cf0-11bd-b23e-10b96e4ef00d"
    )
