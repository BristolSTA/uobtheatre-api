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
