from unittest.mock import PropertyMock, patch

import pytest
from guardian.shortcuts import assign_perm

from uobtheatre.productions.abilities import (
    AddProduction,
    BookForPerformance,
    EditProduction,
)
from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "society_permissions,global_permissions,is_superuser,expected_user_has",
    [
        ([], [], False, False),
        ([], [], True, True),
        (["add_production"], [], False, True),
        ([], ["societies.add_production"], False, True),
        ([], ["productions.add_production"], False, True),
    ],
)
def test_add_production(
    society_permissions, global_permissions, is_superuser, expected_user_has
):
    user = UserFactory(is_superuser=is_superuser)
    society = SocietyFactory()

    for perm in society_permissions:
        assign_perm(perm, user, society)
    for perm in global_permissions:
        assign_perm(perm, user)

    assert AddProduction.user_has(user) is expected_user_has


@pytest.mark.django_db
@pytest.mark.parametrize(
    "obj_permissions, global_permissions,status, is_superuser, expected_user_has",
    [
        ([], [], "DRAFT", False, False),
        ([], [], "PENDING", False, False),
        ([], [], "DRAFT", True, True),
        ([], [], "PENDING", True, True),
        ([], [], "PUBLISHED", True, True),
        (["productions.change_production"], [], "DRAFT", False, True),
        (["productions.change_production"], [], "PENDING", False, False),
        (["productions.change_production"], [], "PUBLISHED", False, False),
        ([], ["productions.approve_production"], "DRAFT", False, False),
        ([], ["productions.approve_production"], "PENDING", False, True),
        ([], ["productions.approve_production"], "PUBLISHED", False, False),
        ([], ["productions.force_change_production"], "DRAFT", False, True),
        ([], ["productions.force_change_production"], "PENDING", False, True),
        ([], ["productions.force_change_production"], "PUBLISHED", False, True),
    ],
)
def test_edit_production_objects(
    obj_permissions, global_permissions, status, is_superuser, expected_user_has
):
    user = UserFactory(is_superuser=is_superuser)
    production = ProductionFactory(status=status)
    for permission in global_permissions:
        assign_perm(
            permission,
            user,
        )
    for permission in obj_permissions:
        assign_perm(permission, user, production)

    assert EditProduction.user_has_for(user, production) == expected_user_has


@pytest.mark.django_db
def test_book_for_performance_any():
    assert BookForPerformance.user_has(UserFactory()) is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "production_status,production_permissions,global_permissions,expected",
    [
        (Production.Status.DRAFT, [], [], False),
        (Production.Status.PENDING, [], [], False),
        (Production.Status.APPROVED, [], [], False),
        (Production.Status.PUBLISHED, [], [], True),
        (Production.Status.CLOSED, [], [], False),
        (Production.Status.COMPLETE, [], [], False),
        # Make sure global & specific production change perms don't elevate permissions
        (Production.Status.PENDING, [], ["productions.change_production"], False),
        (Production.Status.APPROVED, [], ["productions.change_production"], False),
        (
            Production.Status.APPROVED,
            [],
            ["productions.force_change_production"],
            False,
        ),
        (Production.Status.PUBLISHED, [], ["productions.change_production"], True),
        (
            Production.Status.PUBLISHED,
            [],
            ["productions.force_change_production"],
            True,
        ),
        (Production.Status.PENDING, ["productions.change_production"], [], False),
        (Production.Status.APPROVED, ["productions.change_production"], [], False),
        (
            Production.Status.APPROVED,
            ["productions.force_change_production"],
            [],
            False,
        ),
        (Production.Status.PUBLISHED, ["productions.change_production"], [], True),
        (
            Production.Status.PUBLISHED,
            ["productions.force_change_production"],
            [],
            True,
        ),
        # Make sure global & specific box office perms don't elevate permissions
        (Production.Status.PENDING, [], ["productions.boxoffice"], False),
        (Production.Status.APPROVED, [], ["productions.boxoffice"], False),
        (Production.Status.PUBLISHED, [], ["productions.boxoffice"], True),
        (Production.Status.PENDING, ["productions.boxoffice"], [], False),
        (Production.Status.APPROVED, ["productions.boxoffice"], [], False),
        (Production.Status.PUBLISHED, ["productions.boxoffice"], [], True),
        # Make sure comp ticket perms let you comp early
        (Production.Status.PENDING, [], ["productions.comp_tickets"], False),
        (Production.Status.APPROVED, [], ["productions.comp_tickets"], True),
        (Production.Status.PUBLISHED, [], ["productions.comp_tickets"], True),
        (Production.Status.PENDING, ["productions.comp_tickets"], [], False),
        (Production.Status.APPROVED, ["productions.comp_tickets"], [], True),
        (Production.Status.PUBLISHED, ["productions.comp_tickets"], [], True),
    ],
)
def test_book_for_performance_has_for(
    production_status, production_permissions, global_permissions, expected
):
    user = UserFactory()
    production = ProductionFactory(status=production_status)
    performance = PerformanceFactory(
        production=production,
    )

    for permission in global_permissions:
        assign_perm(
            permission,
            user,
        )
    for permission in production_permissions:
        assign_perm(permission, user, production)

    with patch(
        "uobtheatre.productions.models.Performance.is_bookable",
        new_callable=PropertyMock(return_value=True),
    ):  # Assume that it is always bookable (i.e. not sold out, disabled or finished)
        assert BookForPerformance.user_has_for(user, performance) is expected
