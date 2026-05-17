from types import SimpleNamespace

import pytest
from graphene_django.types import ErrorType
from square.core.api_error import ApiError

from uobtheatre.productions.models import Performance
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    AuthOutput,
    FieldError,
    FormExceptions,
    GQLException,
    GQLExceptions,
    MutationException,
    NonFieldError,
    NotFoundException,
    SafeMutation,
    SquareException,
)


def compare_gql_objects(object1, object2):
    """Compares two graphene objects to ensure they are equal"""
    assert type(object1) == type(
        object2
    )  # pylint: disable=unidiomatic-typecheck

    assert (  # pylint: disable=protected-access
        object1._meta.fields == object2._meta.fields
    )
    for field in object1._meta.fields:  # pylint: disable=protected-access
        assert getattr(object1, field) == getattr(object2, field)


def test_auth_error_handling_failure():
    auth_handling = AuthOutput()
    auth_handling.errors = "error"

    with pytest.raises(Exception):
        auth_handling.resolve_errors(None)


def test_auth_error_handling_no_error():
    auth_handling = AuthOutput()
    auth_handling.errors = None
    assert auth_handling.resolve_errors(None) is None


def test_auth_error_handling_list_with_non_dict_entry():
    auth_handling = AuthOutput()
    auth_handling.errors = ["plain error"]

    errors = auth_handling.resolve_errors(None)

    assert len(errors) == 1
    assert isinstance(errors[0], NonFieldError)
    assert errors[0].message == "plain error"


def test_auth_error_handling_dict_non_field_errors_key():
    auth_handling = AuthOutput()
    auth_handling.errors = {
        "nonFieldErrors": [
            {"message": "problem", "code": "bad_input"},
        ]
    }

    errors = auth_handling.resolve_errors(None)

    assert len(errors) == 1
    assert isinstance(errors[0], NonFieldError)
    assert errors[0].message == "problem"
    assert errors[0].code == "bad_input"


@pytest.mark.django_db
def test_safe_mutation_throws_unknown_exception():
    class SomeMutation(SafeMutation):
        def resolve_mutation(
            cls, info, **inputs
        ):  # pylint: disable=no-self-argument
            # pylint: disable=broad-exception-raised
            raise Exception("Some exception")

    with pytest.raises(Exception, match="Some exception"):
        SomeMutation.mutate(None, None)


@pytest.mark.django_db
def test_safe_mutation_with_object_does_not_exist():
    class SomeMutation(SafeMutation):
        def resolve_mutation(cls, _, **__):  # pylint: disable=no-self-argument
            raise Performance.DoesNotExist()

    response_errors = SomeMutation.mutate(None, None).errors
    assert len(response_errors) == 1
    assert response_errors[0].code == 404


def test_gql_non_field_exception():
    exception = GQLException("Some exception", 500)
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        NonFieldError(message="Some exception", code=500),
    )


@pytest.mark.parametrize(
    "field, code",
    [
        ("booking", "400"),
        ("dateOfBirth", "bad"),
    ],
)
def test_gql_field_exception(field, code):
    exception = GQLException("Some exception", code=code, field=field)
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        FieldError(message="Some exception", code=code, field=field),
    )


def test_gql_exceptions():
    exception = GQLExceptions()
    assert not exception.has_exceptions()

    exception.add_exception(
        GQLException("Some exception", code=400, field="booking")
    )

    assert exception.has_exceptions()
    compare_gql_objects(
        exception.resolve()[0],
        FieldError(message="Some exception", code=400, field="booking"),
    )


def test_square_exception():
    exception = SquareException(
        ApiError(
            status_code=400,
            body={
                "errors": [
                    {
                        "category": "PAYMENT_METHOD_ERROR",
                        "code": "SOMETHING_WRONG",
                        "detail": "Some phrase",
                    }
                ]
            },
        )
    )
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        NonFieldError(
            message="There was an issue processing your payment (SOMETHING_WRONG)",
            code=400,
        ),
    )


def test_square_exception_with_payment_method_error_no_detail():
    exception = SquareException(
        ApiError(
            status_code=400,
            body={
                "errors": [
                    {
                        "category": "PAYMENT_METHOD_ERROR",
                        "code": "SOMETHING_WRONG",
                    }
                ]
            },
        )
    )
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        NonFieldError(
            message="There was an issue processing your payment (SOMETHING_WRONG)",
            code=400,
        ),
    )


@pytest.mark.parametrize(
    "error_code, expected_message",
    [
        (
            "ADDRESS_VERIFICATION_FAILURE",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "CARD_EXPIRED",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "CVV_FAILURE",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "EXPIRATION_FAILURE",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "GENERIC_DECLINE",
            "Square received a decline without any additional information. If the payment information seems correct, contact your card issuer to ask for more information.",
        ),
        (
            "INSUFFICIENT_FUNDS",
            "The funding source has insufficient funds to cover the payment.",
        ),
        (
            "INVALID_EXPIRATION",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "INVALID_CARD",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        ("INVALID_PHONE_NUMBER", "The provided phone number is invalid."),
        (
            "INVALID_PIN",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "PAN_FAILURE",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "TRANSACTION_LIMIT",
            "The card issuer has determined the payment amount is either too high or too low.",
        ),
        (
            "BAD_EXPIRATION",
            "Your card details appear to be incorrect. Please check your details and try again.",
        ),
        (
            "CARD_DECLINED_VERIFICATION_REQUIRED",
            "The payment card was declined with a request for additional verification Square cannot process.",
        ),
        (
            "CHIP_INSERTION_REQUIRED",
            "The card issuer requires the card to be inserted into a chip reader, which Square cannot process.",
        ),
    ],
)
def test_square_exception_user_readable_message(error_code, expected_message):
    exception = SquareException(
        ApiError(
            status_code=400,
            body={
                "errors": [
                    {"category": "PAYMENT_METHOD_ERROR", "code": error_code}
                ]
            },
        )
    )
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        NonFieldError(message=expected_message, code=400),
    )


def test_square_exception_with_non_payment_method_error():
    exception = SquareException(
        ApiError(
            status_code=400,
            body={
                "errors": [
                    {
                        "category": "API_ERROR",
                        "code": "SOMETHING_WRONG",
                        "detail": "Detailed error message",
                    }
                ]
            },
        )
    )
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        NonFieldError(
            message="There was an issue processing your payment (SOMETHING_WRONG)",
            code=400,
        ),
    )


@pytest.mark.parametrize(
    "object_type, object_id, message",
    [
        (None, None, "Object not found"),
        ("Performance", None, "Object not found"),
        (None, 1, "Object not found"),
        ("Performance", 1, "Object Performance 1 not found"),
    ],
)
def test_not_found_exception(object_type, object_id, message):
    assert (
        NotFoundException(object_type=object_type, object_id=object_id).message
        == message
    )


@pytest.mark.parametrize(
    "form_errors, expected_resolve_output",
    [
        (
            [ErrorType(messages=["too long", "too short"], field="field")],
            [
                FieldError(
                    message="too long",
                    field="field",
                ),
                FieldError(
                    message="too short",
                    field="field",
                ),
            ],
        )
    ],
)
def test_form_exceptions(form_errors, expected_resolve_output):
    resolved_exceptions = FormExceptions(form_errors).resolve()
    assert len(resolved_exceptions) == len(expected_resolve_output)

    for exception, expected_exception in zip(
        resolved_exceptions, expected_resolve_output
    ):
        compare_gql_objects(exception, expected_exception)


@pytest.mark.parametrize(
    "exception1, exception2, expect_eq",
    [
        (
            FormExceptions(
                [ErrorType(messages=["too long", "too short"], field="field")]
            ),
            FormExceptions(
                [ErrorType(messages=["too long", "too short"], field="field")]
            ),
            True,
        ),
        (
            AuthorizationException(),
            GQLException(
                message="You are not authorized to perform this action",
                code=403,
            ),
            True,
        ),
        (
            AuthorizationException(),
            GQLException(
                message="You are not authorized to perform this action"
            ),
            False,
        ),
        (
            AuthorizationException(),
            GQLException(
                message="You are not authorized to perform this action",
                code=401,
            ),
            False,
        ),
        (MutationException(), ValueError("Some error"), False),
    ],
)
def test_eq(exception1, exception2, expect_eq):
    assert (exception1 == exception2) == expect_eq
