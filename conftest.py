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


@pytest.fixture
def gql_id():
    return lambda id, node: base64.b64encode(f"{node}:{id}".encode("ascii")).decode(
        "utf-8"
    )
