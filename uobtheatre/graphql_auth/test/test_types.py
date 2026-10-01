import pytest

from uobtheatre.graphql_auth.exceptions import WrongUsageError
from uobtheatre.graphql_auth.types import ExpectedErrorType


def test_expected_error_type_serialize_branches():
    result = ExpectedErrorType.serialize(
        {"__all__": [{"message": "oops", "code": "x"}]}
    )
    assert "nonFieldErrors" in result

    list_result = ExpectedErrorType.serialize(
        [{"message": "invalid", "code": "y"}]
    )
    assert list_result == {
        "nonFieldErrors": [{"message": "invalid", "code": "y"}]
    }

    with pytest.raises(WrongUsageError):
        ExpectedErrorType.serialize("not-a-valid-errors-shape")

    dict_result = ExpectedErrorType.serialize(
        {"email": [{"message": "taken", "code": "taken"}]}
    )
    assert "email" in dict_result
