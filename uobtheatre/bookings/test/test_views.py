import pytest

from uobtheatre.bookings.test.factories import BookingFactory


# @pytest.mark.django_db
# def test_booking_view_get(api_client):

#     bookingTest = BookingFactory()

#     response = api_client.get("/api/v1/bookings/")

#     bookings = [
#         {
#             # "id": venueTest.id,
#             # "name": venueTest.name,
#         },
#     ]

#     assert response.status_code == 200
#     assert response.json()["results"] == bookings
