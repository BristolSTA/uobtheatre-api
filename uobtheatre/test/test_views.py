import pytest


@pytest.mark.parametrize("endpoint", [("venues"), ("societies")])
def test_view_is_read_only(api_client, endpoint):

    response = api_client.post(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client.put(f"/api/v1/{endpoint}/")
    assert response.status_code == 405

    response = api_client.delete(f"/api/v1/{endpoint}/")
    assert response.status_code == 405
