import pytest

from uobtheatre.users.test.factories import UserFactory


@pytest.mark.parametrize("endpoint", [("venues"), ("societies")])
def test_view_is_read_only(api_client, endpoint):

    response = api_client.post(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client.put(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client.delete(f"/api/v1/{endpoint}/")
    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", [("bookings")])
def test_auth_view_is_read_only(api_client_authenticated, endpoint):

    response = api_client_authenticated.post(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client_authenticated.put(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client_authenticated.delete(f"/api/v1/{endpoint}/")
    assert response.status_code == 405


@pytest.mark.parametrize("endpoint", [("bookings")])
def test_requires_authentication(api_client, endpoint):

    response = api_client.post(f"/api/v1/{endpoint}/")
    assert response.status_code == 403
