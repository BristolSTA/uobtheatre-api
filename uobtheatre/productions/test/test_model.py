import datetime
import pytest

from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory


@pytest.mark.django_db
def test_performance_duration():
    start = datetime.datetime(day=2, month=3, year=2020, hour=12, minute=0, second=10)
    end = datetime.datetime(day=3, month=4, year=2021, hour=13, minute=1, second=11)
    performance = PerformanceFactory(start=start, end=end)

    assert performance.duration().total_seconds() == 34304461.0


@pytest.mark.django_db
def test_production_duration():

    production = ProductionFactory()

    # Create a performance with a long duration
    start = datetime.datetime(day=2, month=3, year=2020, hour=12, minute=0, second=10)
    end = datetime.datetime(day=3, month=4, year=2021, hour=13, minute=1, second=11)
    performance_long = PerformanceFactory(start=start, end=end, production=production)

    # Create a performance with a short duration
    start = datetime.datetime(day=2, month=3, year=2020, hour=12, minute=0, second=10)
    end = datetime.datetime(day=2, month=3, year=2020, hour=13, minute=0, second=10)
    performance_short = PerformanceFactory(start=start, end=end, production=production)

    assert production.duration() == performance_short.duration()
