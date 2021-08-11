import base64
from typing import TYPE_CHECKING, Optional
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from graphene.test import Client as GQLClient
from pytest_factoryboy import register

from uobtheatre.schema import schema
from uobtheatre.users.test.factories import UserFactory

if TYPE_CHECKING:
    pass

register(UserFactory)  # fixture is user_factory


@pytest.fixture(scope="session")
def gql_client():
    return GQLClient(schema)


class AuthenticateableGQLClient(GQLClient):
    """
    Graphql client which can be loged in and out.
    """

    def __init__(self, schema, format_error=None, user=None, **execute_options):
        self.request_factory = RequestFactory().get("/")
        self.request_factory.user = user
        super().__init__(schema, format_error, **execute_options)

    @property
    def user(self):
        return self.request_factory.user

    @user.setter
    def user(self, new_user):
        if not new_user:
            self.logout()
        self.request_factory.user = new_user

    def logout(self):
        self.request_factory.user = AnonymousUser()

    def execute(self, query, variable_values=None):
        return super().execute(
            query, context_value=self.request_factory, variable_values=variable_values
        )


@pytest.fixture
def gql_client_flexible():
    return AuthenticateableGQLClient(schema, user=UserFactory())


@pytest.fixture
def gql_id():
    return lambda id, node: base64.b64encode(f"{node}:{id}".encode("ascii")).decode(
        "utf-8"
    )


@pytest.fixture
def mock_square():
    class MockApiResponse:
        def __init__(
            self, reason_phrase="Some phrase", status_code=400, success=False, body=None
        ):
            self.reason_phrase = reason_phrase
            self.status_code = status_code
            self.success = success
            self.body = body

        def is_success(self):
            return self.success

    def mock_client(
        square_client_api,
        method: str,
        body: Optional[dict] = None,
        success: Optional[bool] = None,
        reason_phrase: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        return patch.object(
            square_client_api,
            method,
            lambda *_: MockApiResponse(
                body=body,
                success=success,
                reason_phrase=reason_phrase,
                status_code=status_code,
            ),
        )

    return mock_client
