from unittest.mock import patch

import pytest
from guardian.shortcuts import assign_perm

from uobtheatre.discounts.abilities import CreateConcessionType, ModifyConcessionType
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.productions.abilities import EditProductionObjects
from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "obj_permissions, global_permissions, is_superuser, expected_user_has",
    [
        ([], [], False, False),
        ([], [], True, True),
        (["change_production"], [], False, True),
        ([], ["productions.change_production"], False, True),
    ],
)
def test_create_concession_type_ability(
    obj_permissions, global_permissions, is_superuser, expected_user_has
):
    user = UserFactory(is_superuser=is_superuser)
    production = ProductionFactory()
    for permission in global_permissions:
        assign_perm(
            permission,
            user,
        )
    for permission in obj_permissions:
        assign_perm(permission, user, production)

    assert CreateConcessionType.user_has(user, None) is expected_user_has


@pytest.mark.django_db
def test_modify_concession_type_ability_with_no_perms():
    user = UserFactory()
    concession_type = ConcessionTypeFactory()

    assert ModifyConcessionType.user_has(user, concession_type) is False


@pytest.mark.django_db
def test_modify_concession_type_ability_when_on_another_production():
    user = UserFactory()
    production = ProductionFactory(status=Production.Status.DRAFT)
    user.assign_perm("change_production", production)
    concession_type = ConcessionTypeFactory()

    dis_1 = DiscountFactory()
    dis_1.performances.set([PerformanceFactory(production=production)])
    dis_2 = DiscountFactory()
    dis_2.performances.set([PerformanceFactory()])

    DiscountRequirementFactory(discount=dis_1, concession_type=concession_type)
    DiscountRequirementFactory(discount=dis_2, concession_type=concession_type)

    with patch.object(EditProductionObjects, "user_has", return_value=True) as mock:
        assert ModifyConcessionType.user_has(user, concession_type) is False
        mock.assert_not_called()  # This shouldn't be called because it shouldn't reach this later part of the ability


@pytest.mark.django_db
def test_modify_concession_type_ability_when_only_on_owned_production():
    user = UserFactory()
    production = ProductionFactory()
    user.assign_perm("change_production", production)
    concession_type = ConcessionTypeFactory()

    dis_1 = DiscountFactory()
    dis_1.performances.set([PerformanceFactory(production=production)])

    DiscountRequirementFactory(discount=dis_1, concession_type=concession_type)

    with patch.object(EditProductionObjects, "user_has", return_value=True) as mock:
        assert ModifyConcessionType.user_has(user, concession_type) is True
        mock.assert_called_once_with(user, production)
