import types
from unittest import mock

import pytest

from uobtheatre.graphql_auth.constants import TokenAction
from uobtheatre.graphql_auth.exceptions import TokenScopeError
from uobtheatre.graphql_auth.utils import (
    camelize_form_errors,
    flat_dict,
    get_classes,
    get_token,
    get_token_payload,
    get_token_paylod,
    get_user_by_natural_key,
    normalize_fields,
    revoke_user_refresh_token,
    using_refresh_tokens,
)
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_get_token_round_trip():
    user = UserFactory(email="person@example.com")

    token = get_token(
        user, TokenAction.ACTIVATION, secondary_email="other@example.com"
    )
    payload = get_token_payload(token, TokenAction.ACTIVATION)

    assert payload["email"] == user.email
    assert payload["secondary_email"] == "other@example.com"


@pytest.mark.django_db
def test_get_token_payload_rejects_wrong_scope():
    user = UserFactory()
    token = get_token(user, TokenAction.ACTIVATION)

    with pytest.raises(TokenScopeError):
        get_token_payload(token, TokenAction.PASSWORD_RESET)


@pytest.mark.django_db
def test_get_token_paylod_warns_and_delegates():
    user = UserFactory()
    token = get_token(user, TokenAction.ACTIVATION)

    with pytest.deprecated_call(match="get_token_paylod is deprecated"):
        payload = get_token_paylod(token, TokenAction.ACTIVATION)

    assert payload["email"] == user.email


@pytest.mark.parametrize(
    "value, expected",
    [
        ({"one": "String", "two": "String"}, ["one", "two"]),
        (["one", "two"], ["one", "two"]),
    ],
)
def test_flat_dict(value, expected):
    assert flat_dict(value) == expected


@pytest.mark.parametrize(
    "value, extra_fields, expected",
    [
        (
            {"email": "String"},
            ["username"],
            {"email": "String", "username": "String"},
        ),
        (["email"], ["username"], ["email", "username"]),
    ],
)
def test_normalize_fields(value, extra_fields, expected):
    assert normalize_fields(value, extra_fields) == expected


def test_get_classes_filters_by_type():
    module = types.ModuleType("temp_module")

    class Parent:
        pass

    class Child(Parent):
        pass

    class Other:
        pass

    module.Parent = Parent
    module.Child = Child
    module.Other = Other

    classes = get_classes(module, Parent)

    assert ("Parent", Parent) in classes
    assert ("Child", Child) in classes
    assert ("Other", Other) not in classes


def test_camelize_form_errors_renames_non_field_errors():
    errors = {
        "__all__": ["General error"],
        "first_name": ["Required"],
    }

    result = camelize_form_errors(errors)

    assert result["nonFieldErrors"] == ["General error"]
    assert result["firstName"] == ["Required"]


def test_camelize_form_errors_without_non_field_key():
    errors = {
        "email": ["Already in use"],
    }

    result = camelize_form_errors(errors)

    assert result["email"] == ["Already in use"]


@pytest.mark.parametrize(
    "graphql_jwt, installed_apps, expected",
    [
        ({}, [], False),
        ({"JWT_LONG_RUNNING_REFRESH_TOKEN": True}, [], False),
        (
            {"JWT_LONG_RUNNING_REFRESH_TOKEN": True},
            ["graphql_jwt.refresh_token.apps.RefreshTokenConfig"],
            True,
        ),
    ],
)
@mock.patch("uobtheatre.graphql_auth.utils.django_settings")
def test_using_refresh_tokens(
    mocked_settings,
    graphql_jwt,
    installed_apps,
    expected,
):
    mocked_settings.GRAPHQL_JWT = graphql_jwt
    mocked_settings.INSTALLED_APPS = installed_apps

    assert using_refresh_tokens() is expected


def test_revoke_user_refresh_token_revokes_all_tokens():
    token_ok = mock.Mock()
    token_error = mock.Mock()
    token_error.revoke.side_effect = Exception("broken token")

    user = mock.Mock()
    user.refresh_tokens.all.return_value = [token_ok, token_error]

    with mock.patch(
        "uobtheatre.graphql_auth.utils.using_refresh_tokens", return_value=True
    ):
        revoke_user_refresh_token(user)

    user.refresh_tokens.all.assert_called_once_with()
    token_ok.revoke.assert_called_once_with()
    token_error.revoke.assert_called_once_with()


def test_revoke_user_refresh_token_skips_when_feature_disabled():
    user = mock.Mock()

    with mock.patch(
        "uobtheatre.graphql_auth.utils.using_refresh_tokens",
        return_value=False,
    ):
        revoke_user_refresh_token(user)

    user.refresh_tokens.all.assert_not_called()


@pytest.mark.django_db
def test_get_user_by_natural_key_returns_user_with_status_selected():
    user = UserFactory(email="selected@example.com")

    found = get_user_by_natural_key(user.email)

    assert found is not None
    assert found.id == user.id
    assert found.status is not None


def test_get_token_handles_pk_username_and_get_classes_no_filter():
    class UsernameWithPk:
        pk = 42

    class DummyUser:
        USERNAME_FIELD = "email"
        email = "example@example.com"

        def get_username(self):
            return UsernameWithPk()

    token = get_token(DummyUser(), TokenAction.ACTIVATION)
    payload = get_token_payload(token, TokenAction.ACTIVATION)
    assert payload["email"] == 42

    module = types.ModuleType("temp_module")

    class Alpha:
        pass

    module.Alpha = Alpha
    classes = get_classes(module)
    assert ("Alpha", Alpha) in classes

    imported_classes = get_classes("uobtheatre.graphql_auth.utils")
    assert any(name == "TokenScopeError" for name, _ in imported_classes)
