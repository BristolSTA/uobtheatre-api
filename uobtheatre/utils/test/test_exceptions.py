from types import SimpleNamespace

import pytest
from graphene_django.types import ErrorType

from uobtheatre.payments.test.factories import MockApiResponse
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
    assert type(object1) == type(object2)  # pylint: disable=unidiomatic-typecheck

    assert (
        object1._meta.fields == object2._meta.fields  # pylint: disable=protected-access
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


@pytest.mark.django_db
def test_safe_mutation_throws_unknown_exception():
    class SomeMutation(SafeMutation):
        def resolve_mutation(cls, info, **inputs):  # pylint: disable=no-self-argument
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
        exception.resolve()[0], NonFieldError(message="Some exception", code=500)
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

    exception.add_exception(GQLException("Some exception", code=400, field="booking"))

    assert exception.has_exceptions()
    compare_gql_objects(
        exception.resolve()[0],
        FieldError(message="Some exception", code=400, field="booking"),
    )


def test_square_exception():
    exception = SquareException(MockApiResponse())
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0], NonFieldError(message="Some phrase", code=400)
    )


def test_square_exception_with_payment_method_error():
    exception = SquareException(
        MockApiResponse(
            errors=[
                {
                    "category": "PAYMENT_METHOD_ERROR",
                    "code": "SOMETHING_WRONG",
                    "detail": "Detailed error message",
                }
            ]
        )
    )
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        NonFieldError(message="Detailed error message", code=400),
    )


def test_square_exception_with_non_payment_method_error():
    exception = SquareException(
        MockApiResponse(
            errors=[
                {
                    "category": "API_ERROR",
                    "code": "SOMETHING_WRONG",
                    "detail": "Detailed error message",
                }
            ]
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
                message="You are not authorized to perform this action", code=403
            ),
            True,
        ),
        (
            AuthorizationException(),
            GQLException(message="You are not authorized to perform this action"),
            False,
        ),
        (
            AuthorizationException(),
            GQLException(
                message="You are not authorized to perform this action", code=401
            ),
            False,
        ),
        (MutationException(), ValueError("Some error"), False),
    ],
)
def test_eq(exception1, exception2, expect_eq):
    assert (exception1 == exception2) == expect_eq


def test_square_exception_args():
    exc = SquareException(
        SimpleNamespace(
            errors=[{"detail": "abc", "category": "PAYMENT_METHOD_ERROR"}],
            status_code=200,
        )
    )
    assert exc.args == ("abc", 200, None, None)
    assert str(exc) == "('abc', 200, None, None)"
