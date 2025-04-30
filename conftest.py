from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from graphene.test import Client as GQLClient
from rest_framework.test import APIClient
from square import Square as Client
from square.core.api_error import ApiError

from uobtheatre.schema import schema as app_schema
from uobtheatre.users.test.factories import UserFactory


@pytest.fixture
def gql_client():
    return AuthenticateableGQLClient(app_schema)


@pytest.fixture
def rest_client():
    return APIClient()


class AuthenticateableGQLClient(GQLClient):
    """
    Graphql client which can be logged in and out.
    """

    def __init__(self, schema, format_error=None, user=None, **execute_options):
        self.request_factory = RequestFactory().get("/")
        self.request_factory.user = user if user else AnonymousUser()
        super().__init__(schema, format_error, **execute_options)

    @property
    def user(self):
        return self.request_factory.user

    @user.setter
    def user(self, new_user):
        if not new_user:
            self.logout()
        self.request_factory.user = new_user

    def login(self, user=None):
        self.user = user if user else UserFactory()
        return self

    def login_as_super_user(self):
        return self.login(UserFactory(is_superuser=True))

    def logout(self):
        self.request_factory.user = AnonymousUser()

    def execute(self, query, variable_values=None):
        return super().execute(
            query, context_value=self.request_factory, variable_values=variable_values
        )


@pytest.fixture
def square_client():
    """Make a square clients"""
    kwargs = {
        "version": "2025-04-16",
        "token": settings.SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],  # type: ignore
        "environment": settings.SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],  # type: ignore
    }

    if square_url := settings.SQUARE_SETTINGS["SQUARE_URL"]:
        kwargs["base_url"] = square_url
    return Client(**kwargs)


@pytest.fixture(scope="session")
def mock_square():
    """
    Used to mock the square client
    """

    default_exception = ApiError(
        status_code=400,
        body={
            "errors": [
                {
                    "category": "",
                    "detail": "",
                    "code": "MY_CODE",
                }
            ]
        },
    )

    @contextmanager
    def mock_client(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        square_client_api,
        method: str,
        response: Optional[Any] = None,
        exception: Optional[Exception] = None,
        throw_default_exception: bool = False,
    ):
        """
        Mock a provided square client object

        Args:
            square_client_api: The square client object to mock
            method: The method to mock
            response: The response to return
            exception: The exception to raise
            throw_default_exception: Whether to throw the default API exception
        """
        with patch.object(
            square_client_api,
            method,
        ) as mocked_square:
            if exception:
                mocked_square.side_effect = exception
            elif throw_default_exception:
                mocked_square.side_effect = default_exception

            mocked_square.return_value = response

            yield mocked_square

    return mock_client


@pytest.fixture
def info():
    return SimpleNamespace(context=SimpleNamespace(user=UserFactory()))
