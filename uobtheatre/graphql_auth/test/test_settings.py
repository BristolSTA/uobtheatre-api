import pytest

from uobtheatre.graphql_auth.settings import (
    GraphQLAuthSettings,
    graphql_auth_settings,
    reload_graphql_auth_settings,
)


@pytest.fixture
def reset_graphql_auth_settings():
    reload_graphql_auth_settings(setting="GRAPHQL_AUTH", value={})
    yield
    reload_graphql_auth_settings(setting="GRAPHQL_AUTH", value={})


def test_graphql_auth_settings_uses_defaults(reset_graphql_auth_settings):
    assert graphql_auth_settings.ALLOW_LOGIN_NOT_VERIFIED is True


def test_graphql_auth_settings_reads_user_overrides(
    reset_graphql_auth_settings,
):
    reload_graphql_auth_settings(
        setting="GRAPHQL_AUTH",
        value={"ALLOW_LOGIN_NOT_VERIFIED": False},
    )

    assert graphql_auth_settings.ALLOW_LOGIN_NOT_VERIFIED is False


def test_graphql_auth_settings_invalid_attr_raises(
    reset_graphql_auth_settings,
):
    with pytest.raises(AttributeError, match="Invalid graphql_auth setting"):
        _ = graphql_auth_settings.NOT_A_REAL_SETTING


def test_graphql_auth_settings_async_email_flag(reset_graphql_auth_settings):
    reload_graphql_auth_settings(
        setting="GRAPHQL_AUTH",
        value={"EMAIL_ASYNC_TASK": "uobtheatre.mail.tasks.send"},
    )
    assert graphql_auth_settings.is_async_email is True

    reload_graphql_auth_settings(
        setting="GRAPHQL_AUTH",
        value={"EMAIL_ASYNC_TASK": True},
    )
    assert graphql_auth_settings.is_async_email is False


def test_settings_constructor_accepts_explicit_user_settings():
    settings = GraphQLAuthSettings(
        user_settings={"ALLOW_LOGIN_NOT_VERIFIED": False},
        defaults={"ALLOW_LOGIN_NOT_VERIFIED": True},
    )

    assert settings._user_settings["ALLOW_LOGIN_NOT_VERIFIED"] is False
    assert settings.ALLOW_LOGIN_NOT_VERIFIED is False
