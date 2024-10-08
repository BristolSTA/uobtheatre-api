from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm

from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.abilities import (
    AbilitiesMixin,
    Ability,
    OpenAdmin,
    OpenBoxoffice,
    PermissionsMixin,
)
from uobtheatre.users.test.factories import GroupFactory, UserFactory


@pytest.mark.django_db
def test_ability_mixin_perms():
    user = UserFactory()
    production = ProductionFactory()

    assign_perm("change_production", user, production)

    with patch.object(OpenBoxoffice, "user_has_for", return_value=True):
        assert (
            user.get_perms(user, production).sort()
            == [
                "admin_open",
                "change_production",
                "boxoffice_open",
            ].sort()
        )


def test_ability_user_has():
    class DummyAbility(Ability):
        pass

    assert DummyAbility.user_has(None) is False


def test_ability_user_has_for():
    class DummyAbility(Ability):
        @classmethod
        def user_has(cls, _):
            return "example"

    assert DummyAbility.user_has_for(None, None) == "example"


@pytest.mark.django_db
def test_open_boxoffice():
    user = UserFactory()
    performance = PerformanceFactory()
    assert not OpenBoxoffice.user_has(user)

    assign_perm("boxoffice", user, performance.production)
    assert OpenBoxoffice.user_has(user)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permissions, is_superuser, expected_user_has",
    [
        ([], True, True),
        ([], False, False),
        (["productions.add_production"], False, True),
        (["productions.change_production"], False, True),
        (["productions.view_production"], False, True),
        (["reports.finance_reports"], False, True),
        (["productions.view_production", "productions.change_production"], False, True),
        (["productions.boxoffice"], False, False),
    ],
)
def test_open_admin(permissions, is_superuser, expected_user_has):
    user = UserFactory(is_superuser=is_superuser)
    for permission in permissions:
        assign_perm(permission, user)

    assert OpenAdmin.user_has(user) == expected_user_has


@pytest.mark.django_db
def test_permissions_mixin_resolve_permissions_with_get_perms(info):
    class TestModelSchema(PermissionsMixin):
        def get_perms(self, _):
            pass

        class Meta:
            model = Production

    schema = TestModelSchema()
    with patch.object(schema, "get_perms") as mock_get_perms, patch(
        "uobtheatre.users.abilities.get_perms"
    ) as mock_guardian_get_perms, patch.object(
        ContentType.objects,
        "get_for_model",
        return_value=ContentType.objects.get_for_model(Production),
    ):
        schema.resolve_permissions(info)
        mock_get_perms.assert_called_once_with(info.context.user, schema)
        mock_guardian_get_perms.assert_not_called()


@pytest.mark.django_db
def test_permissions_mixin_resolve_permissions_without_get_perms(info):
    class TestModelSchema(PermissionsMixin):
        class Meta:
            model = Production

    schema = TestModelSchema()
    with patch("uobtheatre.users.abilities.get_perms") as mock_get_perms, patch.object(
        ContentType.objects,
        "get_for_model",
        return_value=ContentType.objects.get_for_model(Production),
    ):
        schema.resolve_permissions(info)
        mock_get_perms.assert_called_once_with(info.context.user, schema)


@pytest.mark.django_db
def test_permissions_mixin_resolve_permissions_with_groups(info):
    class TestModelSchema(PermissionsMixin):
        class Meta:
            model = Production

    model = ProductionFactory()
    group = GroupFactory()
    info.context.user.groups.add(group)
    assign_perm("productions.view_production", group)
    info.context.user.assign_perm("productions.approve_production")
    info.context.user.assign_perm("productions.boxoffice", model)

    result = TestModelSchema.resolve_permissions(model, info)
    assert set(result) == set(
        [
            "view_production",
            "approve_production",
            "boxoffice",
        ]
    )
