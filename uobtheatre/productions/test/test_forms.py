from datetime import datetime, timedelta

import pytest
from pytest_django.asserts import assertQuerysetEqual

from uobtheatre.productions.forms import PerformanceForm, ProductionForm
from uobtheatre.productions.models import ProductionContentWarning
from uobtheatre.productions.test.factories import (
    ContentWarningFactory,
    ProductionContentWarningFactory,
    ProductionFactory,
)
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_production_form_invalid_warning_id():
    production = ProductionFactory()
    form = ProductionForm(
        data={
            "contentWarnings": [{"id": "1234"}],
            "production": production.id,
        },
        instance=production,
    )

    assert form.errors == {"contentWarnings": ["A warning with ID 1234 does not exist"]}


@pytest.mark.django_db
def test_production_form_empty_warnings_list():
    production = ProductionFactory()
    warning = ContentWarningFactory()
    ProductionContentWarning.objects.create(warning=warning, production=production)

    assertQuerysetEqual(production.content_warnings.all(), [warning])

    form = ProductionForm(
        data={
            "contentWarnings": [],
            "production": production.id,
        },
        instance=production,
    )

    form.save()
    assertQuerysetEqual(production.content_warnings.all(), [])


@pytest.mark.django_db
def test_production_form_null_warnings():
    pivot = ProductionContentWarningFactory()

    assertQuerysetEqual(pivot.production.content_warnings.all(), [pivot.warning])

    form = ProductionForm(
        data={
            "contentWarnings": None,
            "production": pivot.production.id,
        },
        instance=pivot.production,
    )

    form.save()
    assertQuerysetEqual(pivot.production.content_warnings.all(), [pivot.warning])


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
