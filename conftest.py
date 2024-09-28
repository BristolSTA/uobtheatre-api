from contextlib import contextmanager
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from graphene.test import Client as GQLClient
from rest_framework.test import APIClient
from square.client import Client

from uobtheatre.payments.test.factories import MockApiResponse
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
        "square_version": "2020-11-18",
        "access_token": settings.SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],  # type: ignore
        "environment": settings.SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],  # type: ignore
    }

    if square_url := settings.SQUARE_SETTINGS["SQUARE_URL"]:
        kwargs["custom_url"] = square_url
    return Client(**kwargs)


@pytest.fixture(scope="session")
def mock_square():
    """
    Used to mock the square client
    """

    @contextmanager
    def mock_client(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        square_client_api,
        method: str,
        body: Optional[dict] = None,
        success: Optional[bool] = None,
        reason_phrase: Optional[str] = None,
        status_code: Optional[int] = None,
        errors: Optional[List] = None,
    ):
        """
        Mock a provided square client object
        """
        with patch.object(
            square_client_api,
            method,
        ) as mocked_square:
            mocked_square.return_value = MockApiResponse(
                body=body,
                success=success,
                reason_phrase=reason_phrase,
                status_code=status_code,
                errors=errors,
            )
            yield mocked_square

    return mock_client


@pytest.fixture
def info():
    return SimpleNamespace(context=SimpleNamespace(user=UserFactory()))
