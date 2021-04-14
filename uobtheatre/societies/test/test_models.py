import pytest

from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.societies.test.factories import SocietyFactory


@pytest.mark.django_db
def test_str_society():
    society = SocietyFactory()
    assert str(society) == society.name


@pytest.mark.django_db
def test_str_prod():
    ProductionFactory()
