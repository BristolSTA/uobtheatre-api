from datetime import datetime, timedelta

import pytest

from uobtheatre.productions.forms import PerformanceForm, ProductionForm
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_production_form_invalid_warning_id():
    production = ProductionFactory()
    form = ProductionForm(
        data={
            "warnings": [{"id": "1234"}],
            "production": production.id,
        },
        instance=production,
    )

    assert form.errors == {"warnings": ["A warning with ID 1234 does not exist"]}


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "interval_length, performance_duration, error_message",
    [
        [None, 60, None],
        [10, 60, None],
        [59, 60, None],
        [
            60,
            60,
            "The length of the interval must be less than the length of the performance",
        ],
        [
            61,
            60,
            "The length of the interval must be less than the length of the performance",
        ],
        [
            121,
            240,
            "Ensure this value is less than or equal to 120.",
        ],
        [
            0,
            240,
            "Ensure this value is greater than or equal to 1.",
        ],
    ],
)
def test_performance_interval_length(
    interval_length, performance_duration, error_message
):
    form = PerformanceForm(
        data={
            "start": datetime(2020, 1, 2, 0, 0, 0).isoformat(),
            "end": (
                datetime(2020, 1, 2, 0, 0, 0) + timedelta(minutes=performance_duration)
            ).isoformat(),
            "interval_duration_mins": interval_length,
            "doors_open": datetime(2020, 1, 1, 0, 0, 0).isoformat(),
            "venue": VenueFactory().id,
            "production": ProductionFactory().id,
        }
    )
    if error_message:
        assert form.errors == {"interval_duration_mins": [error_message]}
    else:
        assert form.errors == {}
