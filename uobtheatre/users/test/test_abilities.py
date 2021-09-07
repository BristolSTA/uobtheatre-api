from unittest.mock import patch

import pytest
from guardian.shortcuts import assign_perm

from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.abilities import OpenAdmin, OpenBoxoffice, PermissionsMixin
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_open_boxoffice():
    user = UserFactory()
    performance = PerformanceFactory()
    assert not OpenBoxoffice.user_has(user, None)

    assign_perm("boxoffice", user, performance.production)
    assert OpenBoxoffice.user_has(user, None)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permissions, is_superuser, expected_user_has",
    [
        ([], True, True),
        ([], False, False),
        (["productions.add_production"], False, True),
        (["productions.change_production"], False, True),
        (["productions.view_production"], False, True),
        (["productions.boxoffice"], False, False),
    ],
)
def test_open_admin(permissions, is_superuser, expected_user_has):
    user = UserFactory()
    if is_superuser:
        user.is_superuser = True
        user.save()
    for permission in permissions:
        assign_perm(permission, user)

    assert OpenAdmin.user_has(user, None) == expected_user_has


@pytest.mark.django_db
def test_permissions_mixin_resolve_permissions_with_get_perms(info):
    class TestModelSchema(PermissionsMixin):
        def get_perms(self, _):
            pass

    schema = TestModelSchema()
    with patch.object(schema, "get_perms") as mock_get_perms, patch(
        "uobtheatre.users.abilities.get_perms"
    ) as mock_guardian_get_perms:
        schema.resolve_permissions(info)
        mock_get_perms.assert_called_once_with(info.context.user, schema)
        mock_guardian_get_perms.assert_not_called()


@pytest.mark.django_db
def test_permissions_mixin_resolve_permissions_without_get_perms(info):
    class TestModelSchema(PermissionsMixin):
        pass

    schema = TestModelSchema()
    with patch("uobtheatre.users.abilities.get_perms") as mock_get_perms:
        schema.resolve_permissions(info)
        mock_get_perms.assert_called_once_with(info.context.user, schema)
