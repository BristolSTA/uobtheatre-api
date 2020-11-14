import pytest

from uobtheatre.societies.test.factories import (
    SocietyFactory,
)


@pytest.mark.django_db
def test_society_view_get(api_client):

    socTest = SocietyFactory()

    response = api_client.get("/api/v1/societies/")

    socities = [
        {
            "id": socTest.id,
            "name": socTest.name,
        },
    ]

    assert response.status_code == 200
    assert response.json()["results"] == socities


def test_society_view_is_read_only(api_client):

    response = api_client.post("/api/v1/societies/")
    assert response.status_code == 405

    response = api_client.put("/api/v1/societies/")
    assert response.status_code == 405

    response = api_client.delete("/api/v1/societies/")
    assert response.status_code == 405
