import pytest

from uobtheatre.bookings.test.factories import BookingFactory

ALL_HTTP_VERBS = ["GET", "POST", "PUT", "DELETE", "PATCH"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "endpoint, allowed_verbs, auth_required, factory, factory_parameters",
    [
        ("venues", ["GET"], False, None, None),
        ("societies", ["GET"], False, None, None),
        ("bookings", ["GET", "POST"], True, None, None),
        (
            "bookings/1",
            ["GET", "PATCH", "PUT"],
            True,
            BookingFactory,
            {"id": 1},
        ),
        ("users", ["POST"], False, None, None),
        ("productions", ["GET", "POST"], False, None, None),
    ],
)
def test_views_only_allowed_required_verbs(
    api_client,
    api_client_authenticated,
    endpoint,
    allowed_verbs,
    auth_required,
    factory,
    factory_parameters,
):
    if factory:
        factory(**factory_parameters)

    client = api_client if not auth_required else api_client_authenticated
    disabled_verbs = [verb for verb in ALL_HTTP_VERBS if verb not in allowed_verbs]

    for verb in disabled_verbs:
        response = getattr(client, verb.lower())(f"/api/v1/{endpoint}/")
        assert response.status_code == 405

    for verb in allowed_verbs:
        response = getattr(client, verb.lower())(f"/api/v1/{endpoint}/")
        assert response.status_code != 405


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", [("bookings")])
def test_requires_authentication(api_client, endpoint):

    response = api_client.post(f"/api/v1/{endpoint}/")
    assert response.status_code == 403
