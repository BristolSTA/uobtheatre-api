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
def test_auth_view_is_read_only(api_client, endpoint):

    user = UserFactory()

    api_client.force_authenticate(user=user)

    response = api_client.post(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client.put(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client.delete(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    api_client.force_authenticate(user=None)


@pytest.mark.parametrize("endpoint", [("bookings")])
def test_requires_authentication(api_client, endpoint):

    response = api_client.post(f"/api/v1/{endpoint}/")
    assert response.status_code == 403
