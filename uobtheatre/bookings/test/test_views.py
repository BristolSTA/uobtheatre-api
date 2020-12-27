import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import (BookingFactory,
                                                ConcessionTypeFactory,
                                                TicketFactory)
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_booking_view_only_returns_users_bookings(api_client_flexible):

    user_booking = UserFactory()
    bookingTest = BookingFactory(user=user_booking)

    user_nobooking = UserFactory()

    api_client_flexible.authenticate()
    response = api_client_flexible.get("/api/v1/bookings/")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

    api_client_flexible.authenticate(user=user_booking)
    response = api_client_flexible.get("/api/v1/bookings/")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["user_id"] == user_booking.id


@pytest.mark.django_db
def test_booking_view_get(api_client_flexible, date_format):

    api_client_flexible.authenticate()
    bookingTest = BookingFactory(user=api_client_flexible.user)

    response = api_client_flexible.get("/api/v1/bookings/")

    performance = {
        "id": bookingTest.performance.id,
        "production_id": bookingTest.performance.production.id,
        "venue": {
            "id": bookingTest.performance.venue.id,
            "name": bookingTest.performance.venue.name,
            "slug": bookingTest.performance.venue.slug,
        },
        "extra_information": bookingTest.performance.extra_information,
        "start": bookingTest.performance.start.strftime(date_format),
        "end": bookingTest.performance.end.strftime(date_format),
    }

    bookings = [
        {
            "id": bookingTest.id,
            "user_id": str(api_client_flexible.user.id),
            "booking_reference": str(bookingTest.booking_reference),
            "performance": performance,
        }
    ]

    assert response.status_code == 200
    assert response.json()["results"] == bookings


@pytest.mark.django_db
def test_booking_view_post(api_client_flexible):

    api_client_flexible.authenticate()

    performance = PerformanceFactory()
    seat_group = SeatGroupFactory()
    concession_type = ConcessionTypeFactory()

    body = {
        "performance_id": performance.id,
        "tickets": [
            {"seat_group_id": seat_group.id, "concession_type_id": concession_type.id}
        ],
    }

    # Create booking at get that created booking
    response = api_client_flexible.post("/api/v1/bookings/", body, format="json")
    print(response.json())
    print(body)
    assert response.status_code == 201

    created_booking = Booking.objects.first()

    assert str(created_booking.user.id) == str(api_client_flexible.user.id)
    assert created_booking.performance.id == performance.id
    assert created_booking.tickets.first().seat_group.id == seat_group.id
    assert created_booking.tickets.first().concession_type.id == concession_type.id
