import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.users.test.factories import UserFactory

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S+0000"


@pytest.mark.django_db
def test_booking_view_only_returns_users_bookings(api_client):

    user_booking = UserFactory()
    bookingTest = BookingFactory(user=user_booking)

    user_nobooking = UserFactory()

    api_client.force_authenticate(user=user_nobooking)

    response = api_client.get("/api/v1/bookings/")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

    api_client.force_authenticate(user=user_booking)
    response = api_client.get("/api/v1/bookings/")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["user"] == user_booking.id

    api_client.force_authenticate(user=None)


@pytest.mark.django_db
def test_booking_view_get(api_client):

    user = UserFactory()
    bookingTest = BookingFactory(user=user)

    api_client.force_authenticate(user=user)

    response = api_client.get("/api/v1/bookings/")

    performance = {
        "id": bookingTest.performance.id,
        "production": bookingTest.performance.production.id,
        "venue": {
            "id": bookingTest.performance.venue.id,
            "name": bookingTest.performance.venue.name,
        },
        "extra_information": bookingTest.performance.extra_information,
        "start": bookingTest.performance.start.strftime(DATE_FORMAT),
        "end": bookingTest.performance.end.strftime(DATE_FORMAT),
    }

    bookings = [
        {
            "id": bookingTest.id,
            "user": str(user.id),
            "booking_reference": str(bookingTest.booking_reference),
            "performance": performance,
        }
    ]

    assert response.status_code == 200
    assert response.json()["results"] == bookings

    api_client.force_authenticate(user=None)
