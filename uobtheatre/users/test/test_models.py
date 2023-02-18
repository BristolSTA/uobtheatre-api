import pytest
from django.contrib.auth.models import Group, Permission
from guardian.shortcuts import assign_perm
from pytest_django.asserts import assertQuerysetEqual

from conftest import AuthenticateableGQLClient
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.users.models import User
from uobtheatre.users.test.factories import GroupFactory, UserFactory


@pytest.mark.django_db
def test_str_user():
    user = UserFactory(first_name="Alex", last_name="Smith")
    assert str(user) == "Alex Smith"


@pytest.mark.django_db
def test_has_perm_via_direct():
    user = UserFactory()
    production = ProductionFactory()

    assign_perm("productions.change_production", user)

    assert user.has_perm("change_production", production)
    assert user.has_perm("productions.change_production", production)


@pytest.mark.django_db
def test_has_perm_via_object():
    user = UserFactory()
    production = ProductionFactory()

    assign_perm("productions.change_production", user, production)

    assert user.has_perm("change_production", production)
    assert user.has_perm("productions.change_production", production)

@pytest.mark.django_db
def test_has_perm_via_group():
    user = UserFactory()
    production = ProductionFactory()
    group = GroupFactory()
    group.user_set.add(user)

    assign_perm("productions.change_production", group)

    assert user.has_perm("change_production", production)
    assert user.has_perm("productions.change_production", production)


@pytest.mark.django_db
def test_boxoffice_permissions_object_level(
    gql_client: AuthenticateableGQLClient,
):
    production = ProductionFactory()
    production2 = ProductionFactory()
    user = gql_client.user
    assert not user.has_perm("productions.boxoffice", production)
    assert not user.has_perm("productions.boxoffice", production2)

    assign_perm("boxoffice", user, production)
    assert user.has_perm("boxoffice", production)
    assert not user.has_perm("boxoffice", production2)


@pytest.mark.django_db
def test_boxoffice_permissions_model_level(
    gql_client: AuthenticateableGQLClient,
):
    production = ProductionFactory()
    user = gql_client.login().user
    assert not user.has_perm("productions.boxoffice")
    assert not user.has_perm("productions.boxoffice", production)

    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    user.user_permissions.add(boxoffice_perm)
    user = User.objects.get(pk=user.pk)

    assert user.has_perm("productions.boxoffice")
    assert user.has_perm("productions.boxoffice", production)


@pytest.mark.django_db
def test_boxoffice_permissions_model_level_group(
    gql_client: AuthenticateableGQLClient,
):
    production = ProductionFactory()
    group = Group.objects.create(name="TestGroup")
    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    group.permissions.add(boxoffice_perm)

    user = gql_client.login().user
    assert not user.has_perm("productions.boxoffice", production)

    user.groups.add(group)
    user = User.objects.get(pk=user.pk)

    assert user.has_perm("productions.boxoffice")
    assert user.has_perm("productions.boxoffice", production)


@pytest.mark.django_db
def test_user_get_global_permissions():
    group = GroupFactory()
    user = UserFactory.create(groups=[group])
    assign_perm("productions.boxoffice", user)
    assign_perm("reports.finance_reports", group)

    assert {perm.codename for perm in user.global_perms} == {
        "boxoffice",
        "finance_reports",
    }


@pytest.mark.django_db
def test_user_get_global_permissions_superuser():
    user = UserFactory(is_superuser=True)
    assertQuerysetEqual(user.global_perms, Permission.objects.all())


@pytest.mark.django_db
@pytest.mark.parametrize(
    "global_perms,object_perms,query_perms,expected",
    [
        (["productions.approve_production"], [], ["productions.add_production"], False),
        (["productions.approve_production"], [], "productions.add_production", False),
        (["productions.approve_production"], [], "societies.add_production", False),
        (["societies.add_production"], [], "societies.add_production", True),
        (
            ["productions.approve_production"],
            [],
            ["productions.approve_production"],
            True,
        ),
        (
            ["productions.approve_production"],
            [],
            "productions.approve_production",
            True,
        ),
        (
            ["productions.approve_production"],
            [],
            ["productions.approve_production", "productions.add_production"],
            True,
        ),
        ([], ["productions.add_production"], ["productions.approve_production"], False),
        ([], ["productions.add_production"], ["productions.add_production"], True),
        (
            [],
            ["productions.add_production"],
            ["productions.approve_production", "productions.add_production"],
            True,
        ),
    ],
)
def test_user_has_any_objects_with_perms(
    global_perms, object_perms, query_perms, expected
):
    user = UserFactory()
    for perm in global_perms:
        user.assign_perm(perm)

    if len(object_perms):
        obj = ProductionFactory()
        for perm in object_perms:
            user.assign_perm(perm, obj)

    assert user.has_any_objects_with_perms(query_perms) is expected
