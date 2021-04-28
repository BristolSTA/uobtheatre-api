import base64

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from graphene.test import Client as GQLClient
from pytest_factoryboy import register

from uobtheatre.schema import schema
from uobtheatre.users.test.factories import UserFactory

register(UserFactory)  # fixture is user_factory


@pytest.fixture(scope="session")
def gql_client():
    return GQLClient(schema)


class AuthenticateableGQLClient(GQLClient):
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
def gql_client_flexible(user_factory):
    return AuthenticateableGQLClient(schema, user=user_factory())


@pytest.fixture
def gql_id():
    return lambda id, node: base64.b64encode(f"{node}:{id}".encode("ascii")).decode(
        "utf-8"
    )


@pytest.fixture
def mock_square(monkeypatch):
    class MockApiResponse:
        def __init__(self):
            self.reason_phrase = "Some phrase"
            self.status_code = 400
            self.success = False
            self.body = None

        def is_success(self):
            return self.success

    def mock_create_payment(value, indeptency_key, nonce):
        return mock_api_response

    monkeypatch.setattr(
        "uobtheatre.bookings.models.PaymentProvider.create_payment", mock_create_payment
    )

    mock_api_response = MockApiResponse()
    return mock_api_response
