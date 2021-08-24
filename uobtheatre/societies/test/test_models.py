import pytest

from uobtheatre.societies.test.factories import SocietyFactory


@pytest.mark.django_db
def test_str_society():
    society = SocietyFactory()
    assert str(society) == society.name


@pytest.mark.django_db
def test_autoslug_doesnot_change_on_update():
    society = SocietyFactory(name="abc")
    initial_slug = society

    society.name = "def"
    society.save()
    society.refresh_from_db()
    assert society.slug == initial_slug
