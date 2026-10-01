import uuid
from unittest import mock

import pytest
from django.core.exceptions import ObjectDoesNotExist

from uobtheatre.graphql_auth import shortcuts
from uobtheatre.graphql_auth.settings import reload_graphql_auth_settings
from uobtheatre.graphql_auth.types import ExpectedErrorType
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_shortcuts_cover_custom_type_async_and_username_login_paths():
    user = UserFactory()
    assert shortcuts.get_user_to_login(id=user.id).id == user.id

    reload_graphql_auth_settings(
        setting="GRAPHQL_AUTH",
        value={
            "EMAIL_ASYNC_TASK": "uobtheatre.graphql_auth.shortcuts.get_output_error_type"
        },
    )
    try:
        async_func = shortcuts.get_async_email_func()
    finally:
        reload_graphql_auth_settings(setting="GRAPHQL_AUTH", value={})
    assert callable(async_func)

    with mock.patch.object(
        shortcuts.app_settings,
        "CUSTOM_ERROR_TYPE",
        "uobtheatre.graphql_auth.types.ExpectedErrorType",
    ):
        assert shortcuts.get_output_error_type() is ExpectedErrorType

    with pytest.raises(ObjectDoesNotExist):
        shortcuts.get_user_to_login(id=uuid.uuid4())


@pytest.mark.django_db
def test_shortcuts_login_email_branch_without_secondary_email(monkeypatch):
    user = UserFactory(email="primary-only@example.com")
    monkeypatch.setattr(
        shortcuts.app_settings,
        "ALLOW_LOGIN_WITH_SECONDARY_EMAIL",
        False,
    )
    found = shortcuts.get_user_to_login(email="primary-only@example.com")
    assert found.id == user.id
