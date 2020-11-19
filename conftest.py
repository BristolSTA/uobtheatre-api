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
    api_client.force_authenticate(user=user_factory())
    # Yield to the test
    yield api_client
    # Unauth the user
    api_client.force_authenticate(user=None)


@pytest.fixture
def date_format():
    DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
    return DATE_FORMAT


@pytest.fixture
def date_format_2():
    DATE_FORMAT = "%Y-%m-%dT%H:%M:%S+0000"
    return DATE_FORMAT
