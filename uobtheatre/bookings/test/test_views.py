import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_booking_view_get(api_client):

    user = UserFactory()

    api_client.force_authenticate(user=user)

    bookingTest = BookingFactory()

    response = api_client.get("/api/v1/bookings/")

    bookings = [
        {
            # "id": venueTest.id,
            # "name": venueTest.name,
        },
    ]

    assert response.status_code == 200
    assert response.json()["results"] == bookings

    api_client.force_authenticate(user=None)
