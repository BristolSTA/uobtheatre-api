import pytest

from uobtheatre.venues.test.factories import VenueFactory, SeatGroupFactory


@pytest.mark.django_db
def test_str_venue():
    venue = VenueFactory()
    assert str(venue) == venue.name


@pytest.mark.django_db
def test_str_seat_group():
    seat_group = SeatGroupFactory()
    assert str(seat_group) == seat_group.name

    seat_group.name = None
    assert str(seat_group) == str(seat_group.id)
