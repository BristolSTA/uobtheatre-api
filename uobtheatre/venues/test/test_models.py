import pytest

from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.venues.test.factories import SeatGroupFactory, VenueFactory


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


@pytest.mark.django_db
def test_venue_productions():
    venue1 = VenueFactory()
    venue2 = VenueFactory()
    production_1 = ProductionFactory()
    production_2 = ProductionFactory()

    PerformanceFactory(production=production_1, venue=venue1)
    PerformanceFactory(production=production_1, venue=venue1) # Catching productions being duplicated by .fliter() when there are multiple performance in the same venue
    PerformanceFactory(production=production_1, venue=venue2)
    PerformanceFactory(production=production_2, venue=venue2)

    assert len(venue1.get_productions()) == 1
    assert len(venue2.get_productions()) == 2
