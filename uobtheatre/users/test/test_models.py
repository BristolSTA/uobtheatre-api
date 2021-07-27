import pytest
from django.contrib.auth.models import Group, Permission
from guardian.shortcuts import assign_perm

from conftest import AuthenticateableGQLClient
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.models import User
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_str_user():
    user = UserFactory(first_name="Alex", last_name="Smith")
    assert str(user) == "Alex Smith"


@pytest.mark.django_db
def test_boxoffice_permissions_object_level(
    gql_client_flexible: AuthenticateableGQLClient,
):
    production = ProductionFactory()
    production2 = ProductionFactory()
    user = gql_client_flexible.user
    assert not user.has_perm("productions.boxoffice", production)
    assert not user.has_perm("productions.boxoffice", production2)

    assign_perm("boxoffice", user, production)
    assert user.has_perm("boxoffice", production)
    assert not user.has_perm("boxoffice", production2)


@pytest.mark.django_db
def test_boxoffice_permissions_model_level(
    gql_client_flexible: AuthenticateableGQLClient,
):
    production = ProductionFactory()
    user = gql_client_flexible.user
    assert not user.has_perm("productions.boxoffice")
    assert not user.has_perm("productions.boxoffice", production)

    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    user.user_permissions.add(boxoffice_perm)
    user = User.objects.get(pk=user.pk)

    assert user.has_perm("productions.boxoffice")
    assert user.has_perm("productions.boxoffice", production)


@pytest.mark.django_db
def test_boxoffice_permissions_model_level_group(
    gql_client_flexible: AuthenticateableGQLClient,
):
    production = ProductionFactory()
    group = Group.objects.create(name="TestGroup")
    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    group.permissions.add(boxoffice_perm)

    user = gql_client_flexible.user
    assert not user.has_perm("productions.boxoffice", production)

    user.groups.add(group)
    user = User.objects.get(pk=user.pk)

    assert user.has_perm("productions.boxoffice")
    assert user.has_perm("productions.boxoffice", production)


@pytest.mark.django_db
def test_can_boxoffice():
    performance = PerformanceFactory()
    PerformanceFactory()

    user = UserFactory()
    assert not user.can_boxoffice

    assign_perm("boxoffice", user, performance.production)
    assert user.can_boxoffice
