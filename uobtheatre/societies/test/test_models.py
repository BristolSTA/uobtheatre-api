import pytest

from uobtheatre.societies.test.factories import SocietyFactory


@pytest.mark.django_db
def test_str_society():
    society = SocietyFactory()
    assert str(society) == society.name
