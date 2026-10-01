import importlib
from unittest import mock

from uobtheatre.graphql_auth import mutations, relay


def test_relay_and_mutations_field_helpers_exercise_token_branches():
    importlib.reload(relay)
    importlib.reload(mutations)

    with mock.patch.object(
        relay.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        relay.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", True
    ):
        relay.ObtainJSONWebToken.Field()
        relay.RefreshToken.Field()

    with mock.patch.object(
        relay.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", True
    ), mock.patch.object(
        relay.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        relay.ObtainJSONWebToken.Field()
        relay.RefreshToken.Field()

    with mock.patch.object(
        mutations.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        mutations.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", True
    ):
        mutations.ObtainJSONWebToken.Field()
        mutations.RefreshToken.Field()

    with mock.patch.object(
        mutations.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", True
    ), mock.patch.object(
        mutations.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        mutations.ObtainJSONWebToken.Field()
        mutations.RefreshToken.Field()

    with mock.patch.object(
        mutations.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        mutations.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        mutations.ObtainJSONWebToken.Field()
        mutations.RefreshToken.Field()

    with mock.patch.object(
        relay.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        relay.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        relay.ObtainJSONWebToken.Field()
        relay.RefreshToken.Field()
