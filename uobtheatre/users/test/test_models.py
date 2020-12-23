import pytest

from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_str_user():
    user = UserFactory()
    assert str(user) == user.username
