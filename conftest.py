import base64

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from graphene.test import Client as GQLClient
from pytest_factoryboy import register
from rest_framework.test import APIClient

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

    def set_user(self, user):
        if not user:
            self.logout()
        self.request_factory.user = user

    def logout(self):
        self.request_factory.user = AnonymousUser()

    def execute(self, query):
        return super().execute(query, context_value=self.request_factory)


@pytest.fixture
def gql_client_flexible(user_factory):
    return AuthenticateableGQLClient(schema, user=user_factory())


@pytest.fixture(scope="session")
def api_client():
    return APIClient()


@pytest.fixture
def api_client_authenticated(api_client, user_factory):
    # Authenticate user as some random user
    api_client.force_authenticate(user=user_factory())
    # Yield to the test
    yield api_client
    # Unauth the user
    api_client.force_authenticate(user=None)


class AuthenticateableClient(APIClient):
    def __init__(self, user_factory):
        self.user = None
        self.user_factory = user_factory
        super().__init__()

    def authenticate(self, user=None):
        if user is None:
            user = self.user_factory()

        self.user = user

        self.force_authenticate(user=user)

    def unauthenticatae(self):
        self.force_authenticate(user=None)


@pytest.fixture
def api_client_flexible(api_client, user_factory):
    # Authenticate user as some random user
    flexible_client = AuthenticateableClient(user_factory)
    # Yield to the test
    yield flexible_client
    # Unauth the user
    flexible_client.unauthenticatae()


@pytest.fixture
def date_format():
    return "%Y-%m-%dT%H:%M:%SZ"


@pytest.fixture
def gql_id():
    return lambda id, node: base64.b64encode(f"{node}:{id}".encode("ascii")).decode(
        "utf-8"
    )
