import pytest

from uobtheatre.utils.exceptions import (
    AuthOutput,
    FieldError,
    GQLExceptions,
    GQLFieldException,
    GQLNonFieldException,
    NonFieldError,
    SafeMutation,
    SquareException,
)


def compare_gql_objects(object1, object2):
    assert type(object1) == type(object2)
    assert object1._meta.fields == object2._meta.fields


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
        def resolve_mutation(cls, info, **input):
            raise Exception("Some exception")

    with pytest.raises(Exception, match="Some exception"):
        SomeMutation.mutate(None, None)


def test_gql_non_field_exception():
    exception = GQLNonFieldException("Some exception", 500)
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0], NonFieldError(message="Some exception", code=500)
    )


def test_gql_field_exception():
    exception = GQLFieldException("Some exception", code=400, field="booking")
    assert len(exception.resolve()) == 1
    compare_gql_objects(
        exception.resolve()[0],
        FieldError(message="Some exception", code=400, field="booking"),
    )


def test_gql_exceptions():
    exception = GQLExceptions()
    assert not exception.has_exceptions()

    exception.add_exception(
        GQLFieldException("Some exception", code=400, field="booking")
    )

    assert exception.has_exceptions()
    compare_gql_objects(
        exception.resolve()[0],
        FieldError(message="Some exception", code=400, field="booking"),
    )


def test_square_exception():
    class MockApiResponse:
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
