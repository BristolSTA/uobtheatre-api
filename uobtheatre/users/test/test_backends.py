from types import SimpleNamespace
from unittest import mock

import pytest
from graphql_jwt.exceptions import JSONWebTokenError
from rest_framework.exceptions import AuthenticationFailed

from uobtheatre.users.backends import GraphqlJWTAuthentication


@pytest.mark.parametrize(
    "token, get_user_response, raise_jwt_exception, exception, expected_response",
    [
        ("abc", "user", False, None, ("user", None)),
        ("abc", None, False, "User not found", None),
        ("abc", "user", True, "JWT invalid or expired", None),
    ],
)
def test_graphql_jwt_auth_backend(
    token, get_user_response, raise_jwt_exception, exception, expected_response
):
    """
    Test the JWT authentication backend.
    """
    backend = GraphqlJWTAuthentication()
    request = SimpleNamespace(META={"HTTP_AUTHORIZATION": f"JWT {token}"})

    # Test the authenticate method
    with mock.patch(
        "uobtheatre.users.backends.get_user_by_token",
        return_value=get_user_response,
        side_effect=JSONWebTokenError() if raise_jwt_exception else None,
    ) as mock_get_user_by_token:

        if exception:
            with pytest.raises(AuthenticationFailed, match=exception):
                backend.authenticate(request)
        else:
            response = backend.authenticate(request)
            assert response == expected_response

        mock_get_user_by_token.assert_called_once_with(token, request)


@pytest.mark.parametrize(
    "meta, exception",
    [
        ({"HTTP_AUTHORIZATION": "abc"}, "Invalid token"),
        ({}, None),
        ({"HTTP_AUTHORIZATION": None}, None),
        ({"HTTP_AUTHORIZATION": ""}, "Invalid token"),
        ({"HTTP_AUTHORIZATION": "JWT"}, "Invalid token"),
        ({"HTTP_AUTHORIZATION": "JWT "}, "Invalid token"),
        ({"HTTP_AUTHORIZATION": "JWT  "}, "Invalid token"),
    ],
)
def test_graphql_jwt_auth_backend_invalid_header(meta, exception):
    """
    Test the JWT authentication backend.
    """
    backend = GraphqlJWTAuthentication()
    request = SimpleNamespace(META=meta)

    # Test the authenticate method
    with mock.patch(
        "uobtheatre.users.backends.get_user_by_token"
    ) as mock_get_user_by_token:

        if exception:
            with pytest.raises(AuthenticationFailed, match=exception):
                response = backend.authenticate(request)
        else:
            response = backend.authenticate(request)
            assert response is None

        mock_get_user_by_token.assert_not_called()
