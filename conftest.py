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

    def get_user(self):
        return self.request_factory.user

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


@pytest.fixture
def freeze(monkeypatch):
    """Now() manager patches datetime return a fixed, settable, value
    (freezes time)
    """
    import datetime

    original = datetime.datetime

    class FreezeMeta(type):
        def __instancecheck__(self, instance):
            if type(instance) == original or type(instance) == Freeze:
                return True

    class Freeze(datetime.datetime):
        __metaclass__ = FreezeMeta

        @classmethod
        def freeze(cls, val):
            cls.frozen = val

        @classmethod
        def now(cls):
            return cls.frozen

        @classmethod
        def delta(cls, timedelta=None, **kwargs):
            """ Moves time fwd/bwd by the delta"""
            from datetime import timedelta as td

            if not timedelta:
                timedelta = td(**kwargs)
            cls.frozen += timedelta

    monkeypatch.setattr(datetime, "datetime", Freeze)
    Freeze.freeze(original.now())
    return Freeze
