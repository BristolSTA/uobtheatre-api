import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

from uobtheatre.users.test.factories import UserFactory

register(UserFactory)  # fixture is user_factory


@pytest.fixture(scope="session")
def api_client():
    return APIClient()


@pytest.fixture
def api_client_authenticated(api_client, user_factory):
    # Authenticate user as some random user
    api_client.force_authenticate(user=user_factory(user=user))
    # Yield to the test
    yield api_client
    # Unauth the user
    api_client.force_authenticate(user=None)
