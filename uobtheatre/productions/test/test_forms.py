from unittest.mock import patch
import pytest
from datetime import datetime
from uobtheatre.productions.forms import PerformanceForm

from uobtheatre.productions.test.factories import PerformanceFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "door, start, end, error",
    [
        (
            datetime(day=10, month=1, year=2020),
            datetime(day=11, month=1, year=2020),
            datetime(day=12, month=1, year=2020),
            [],
        ),
    ],
)
def test_performance_form_clean(door, start, end, error):
    form = PerformanceForm(
        data={
            "doors_open": door.isoformat(),
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    )

    # Patch super.clean call
    with patch.object(form, "super", return_value=None):
        assert form.errors == error
