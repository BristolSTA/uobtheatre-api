import pytest
from rest_framework.test import APIClient

# from uobtheatre.users.test.factories import UserFactory


@pytest.fixture(scope="session")
def api_client():
    return APIClient()


# @pytest.mark.django_db
# @pytest.fixture(scope="session")
# def api_client_authenticated(pytest.db,api_client):

#     user = UserFactory()

#     api_client.force_authentication(user=user)

#     yield api_client

#     api_client.force_authentication(user=None)
