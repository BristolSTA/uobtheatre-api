import pytest

from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_str_user():
    user = UserFactory(first_name="Alex", last_name="Smith")
    assert str(user) == "Alex Smith"
