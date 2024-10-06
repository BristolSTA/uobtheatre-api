from unittest.mock import patch

import pytest
from django.test import override_settings

from uobtheatre.users.turnstile import SiteVerifyResponse, validate

PASSING_SECRET = "1x0000000000000000000000000000000AA"
FAILING_SECRET = "2x0000000000000000000000000000000AA"
SPEND_SECRET = "3x0000000000000000000000000000000AA"


@override_settings(TURNSTILE_SECRET=None)
@pytest.mark.django_db
def test_validate_no_secret():
    response = validate("dummy_response")
    assert not response.success
    assert response.error_codes and response.error_codes == ["No secret key defined."]


@override_settings(TURNSTILE_SECRET=PASSING_SECRET)
@pytest.mark.django_db
def test_validate_no_response():
    response = validate("")
    assert not response.success
    assert response.error_codes and response.error_codes == [
        "No Turnstile token provided."
    ]


@override_settings(TURNSTILE_SECRET=PASSING_SECRET)
@pytest.mark.django_db
def test_validate_success():
    response = validate("XXXX.DUMMY.TOKEN.XXXX")
    assert response.success


@override_settings(TURNSTILE_SECRET=FAILING_SECRET)
@pytest.mark.django_db
def test_validate_failure():
    response = validate("XXXX.DUMMY.TOKEN.XXXX")
    assert not response.success
    assert response.error_codes and response.error_codes == ["invalid-input-response"]


@override_settings(TURNSTILE_SECRET=SPEND_SECRET)
@pytest.mark.django_db
def test_validate_token_spent():
    response = validate("XXXX.DUMMY.TOKEN.XXXX")
    assert not response.success
    assert response.error_codes and response.error_codes == ["timeout-or-duplicate"]


@patch("uobtheatre.users.turnstile.requests.post")
@pytest.mark.django_db
def test_validate_failure_status_code(mock_post):
    mock_post.return_value.status_code = 400
    mock_post.return_value.text = "Bad Request"

    response = validate("dummy_response")
    assert not response.success
    assert response.error_codes and response.error_codes == [
        "Failure status code: 400",
        "Failure details: Bad Request",
    ]


@patch("uobtheatre.users.turnstile.requests.post")
@pytest.mark.django_db
def test_validate_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    response = validate("dummy_response")
    assert not response.success
    assert response.error_codes and response.error_codes == [
        "Failure status code: Unknown",
        "Failure details: Network error",
    ]
