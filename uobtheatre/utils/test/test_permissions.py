import pytest
from guardian.shortcuts import assign_perm

from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.permissions import get_users_with_perm


@pytest.mark.django_db
def test_get_users_with_perm():
    user_1 = UserFactory(first_name="User", last_name="1")
    user_2 = UserFactory(first_name="User", last_name="2")
    UserFactory()

    production_1 = ProductionFactory()

    assign_perm("productions.change_production", user_1, production_1)
    assign_perm("productions.change_production", user_2)

    result = get_users_with_perm("productions.change_production", production_1)
    assert len(result) == 2
    assert user_1 in result
    assert user_2 in result
