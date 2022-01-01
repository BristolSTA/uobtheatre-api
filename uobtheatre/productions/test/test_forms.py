from datetime import datetime

import pytest

from uobtheatre.productions.forms import PerformanceForm
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "door, start, end, error",
    [
        (
            datetime(day=10, month=1, year=2020),
            datetime(day=11, month=1, year=2020),
            datetime(day=12, month=1, year=2020),
            {},
        ),
        (
            datetime(day=11, month=1, year=2020),
            datetime(day=10, month=1, year=2020),
            datetime(day=12, month=1, year=2020),
            {"doors_open": ["Doors open must be before the start time"]},
        ),
        (
            datetime(day=10, month=1, year=2020),
            datetime(day=11, month=1, year=2020),
            datetime(day=10, month=1, year=2020),
            {"start": ["The start time must be before the end time"]},
        ),
    ],
)
def test_performance_form_clean_timings(door, start, end, error):
    form = PerformanceForm(
        data={
            "doors_open": door.isoformat(),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "venue": VenueFactory().id,
            "production": ProductionFactory().id,
        }
    )

    assert form.errors == error
