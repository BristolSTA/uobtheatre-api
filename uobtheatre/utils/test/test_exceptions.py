import pytest

from uobtheatre.utils.exceptions import AuthOutput


def test_auth_error_handling_failure():
    auth_handling = AuthOutput()
    auth_handling.errors = "error"

    with pytest.raises(Exception):
        auth_handling.resolve_errors(None)


def test_auth_error_handling_no_error():
    auth_handling = AuthOutput()
    auth_handling.errors = None
    assert auth_handling.resolve_errors(None) is None
