import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    ConcessionTypeFactory,
    TicketFactory,
)
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory
from uobtheatre.bookings.serializers import BookingPriceBreakDownSerializer


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
def test_booking_view_get_list(api_client_flexible, date_format):

    api_client_flexible.authenticate()
    booking = BookingFactory(user=api_client_flexible.user)

    response = api_client_flexible.get("/api/v1/bookings/")

    performance = {
        "id": booking.performance.id,
        "production_id": booking.performance.production.id,
        "venue": {
            "id": booking.performance.venue.id,
            "name": booking.performance.venue.name,
            "slug": booking.performance.venue.slug,
        },
        "extra_information": booking.performance.extra_information,
        "start": booking.performance.start.strftime(date_format),
        "end": booking.performance.end.strftime(date_format),
    }

    bookings = [
        {
            "id": booking.id,
            "user_id": str(api_client_flexible.user.id),
            "booking_reference": str(booking.booking_reference),
            "performance": performance,
            "total_price": booking.total(),
        }
    ]

    assert response.status_code == 200
    assert response.json()["results"] == bookings


@pytest.mark.django_db
def test_booking_view_get_details(api_client_flexible, date_format):

    api_client_flexible.authenticate()
    booking = BookingFactory(user=api_client_flexible.user)

    response = api_client_flexible.get(f"/api/v1/bookings/{booking.id}/")

    performance = {
        "id": booking.performance.id,
        "production_id": booking.performance.production.id,
        "venue": {
            "id": booking.performance.venue.id,
            "name": booking.performance.venue.name,
            "slug": booking.performance.venue.slug,
        },
        "extra_information": booking.performance.extra_information,
        "start": booking.performance.start.strftime(date_format),
        "end": booking.performance.end.strftime(date_format),
    }

    price_breakdown = BookingPriceBreakDownSerializer(booking).data

    booking = {
        "id": booking.id,
        "user_id": str(booking.user.id),
        "booking_reference": str(booking.booking_reference),
        "performance": performance,
        "price_breakdown": price_breakdown,
    }

    assert response.status_code == 200
    assert response.json() == booking


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
