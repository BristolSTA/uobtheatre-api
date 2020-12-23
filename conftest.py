import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

from uobtheatre.users.test.factories import UserFactory
from config.settings.common import REST_FRAMEWORK

register(UserFactory)  # fixture is user_factory


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
