from types import SimpleNamespace
from unittest import mock

from graphql_jwt.exceptions import JSONWebTokenError

from uobtheatre.graphql_auth.backends import GraphQLAuthBackend


def test_backend_authenticate_handles_jwt_errors_gracefully():
    request = SimpleNamespace(_jwt_token_auth=False)
    backend = GraphQLAuthBackend()

    with mock.patch(
        "uobtheatre.graphql_auth.backends.get_credentials",
        return_value="jwt-token",
    ), mock.patch(
        "uobtheatre.graphql_auth.backends.get_user_by_token",
        side_effect=JSONWebTokenError("invalid"),
    ):
        assert backend.authenticate(request=request) is None

    with mock.patch(
        "uobtheatre.graphql_auth.backends.get_credentials",
        return_value=None,
    ):
        assert backend.authenticate(request=request) is None
