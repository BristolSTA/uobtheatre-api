import pytest

from uobtheatre.utils.exceptions import (
    AuthOutput,
    FieldError,
    GQLException,
    GQLExceptions,
    NonFieldError,
    SafeMutation,
    SquareException,
)


def compare_gql_objects(object1, object2):
    assert type(object1) == type(object2)  # pylint: disable=unidiomatic-typecheck
    assert (
        object1._meta.fields == object2._meta.fields  # pylint: disable=protected-access
    )


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


def test_gql_non_field_exception():
    exception = GQLException("Some exception", 500)
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0], NonFieldError(message="Some exception", code=500)
    )


@pytest.mark.parametrize(
    "field, resolved_field",
    [
        ("booking", "booking"),
        ("dateOfBirth", "dateOfBirth"),
        ("date_of_birth", "dateOfBirth"),
    ],
)
def test_gql_field_exception(field, resolved_field):
    exception = GQLException("Some exception", code=400, field=field)
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        FieldError(message="Some exception", code=400, field=resolved_field),
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
    class MockApiResponse:  # pylint: disable=missing-class-docstring
        def __init__(self):
            self.reason_phrase = "Some phrase"
            self.status_code = 404

        def is_success(self):
            return False

    exception = SquareException(MockApiResponse())
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0], NonFieldError(message="Some phrase", code=404)
    )
