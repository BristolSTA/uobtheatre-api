import pytest
from rest_framework.exceptions import APIException

from uobtheatre.utils.exceptions import custom_exception_handler


@pytest.mark.parametrize(
    "error, status_code, exception, output_error",
    [
        (["Some error message"], 400, APIException, ["Some error message"]),
        (
            {"error_key": "Some error message"},
            402,
            APIException,
            [{"error_key": "Some error message"}],
        ),
    ],
)
def test_exception_with_list_dict_str(
    error, status_code, exception, output_error, monkeypatch
):
    class mock_response:
        def __init__(self):
            self.data = error
            self.status_code = status_code

    def mock_exception_handler(exception, context):
        return mock_response()

    monkeypatch.setattr(
        "uobtheatre.utils.exceptions.exception_handler", mock_exception_handler
    )

    assert custom_exception_handler(exception(), None).data == {
        "errors": output_error,
        "status_code": status_code,
        "error_type": exception.__name__,
    }


def test_exception_with_None(monkeypatch):
    monkeypatch.setattr(
        "uobtheatre.utils.exceptions.exception_handler", lambda *_: None
    )

    assert custom_exception_handler(APIException(), None) is None
