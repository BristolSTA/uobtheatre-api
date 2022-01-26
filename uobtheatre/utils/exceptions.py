"""
Defines exception handling for the api.
For mutations:
    - Inherit from SafeMutation
    - Raise one of the MutationResult exceptions
    - This will then be caught by SafeMutation and formatted into one of the
      gql error fields (FieldError or NonFieldError) using resolve method.
In general a mutation will also return MutationResult fields (success: bool and
error: Union[FieldError, NonFieldError])
"""


import traceback
from typing import Any, Iterable, List, Union

import graphene
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from graphene.utils.str_converters import to_camel_case
from graphene_django.types import ErrorType


class ExceptionMiddleware:  # pragma: no cover
    """
    Middleware to print exception traceback when an exception is caught by
    graphene.
    """

    def on_error(self, exc):
        traceback.print_tb(exc.__traceback__)
        raise exc

    def resolve(self, next, root, info, **kwargs):  # pylint: disable=redefined-builtin
        return next(root, info, **kwargs).catch(self.on_error)


class NonFieldError(graphene.ObjectType):
    message = graphene.String()
    code = graphene.String()


class FieldError(graphene.ObjectType):
    """
    FieldError is used to return errors which are for a specific field.
    """

    message = graphene.String()
    field = graphene.String()
    code = graphene.String()

    def resolve_field(self, _):
        return to_camel_case(self.field)


class GQLErrorUnion(graphene.Union):
    class Meta:
        types = (FieldError, NonFieldError)


class MutationResult:
    success = graphene.Boolean(default_value=True)
    errors = graphene.List(GQLErrorUnion)


class AuthOutput(MutationResult):
    """
    Overwrites the output class used in graphql_auth. This allows for custom
    error handling.
    """

    def resolve_errors(self, info):
        if self.errors is None:
            return None

        if isinstance(self.errors, list):
            non_field_errors = [
                NonFieldError(error["message"], code=error["code"])
                for error in self.errors  # pylint: disable=E1133
            ]
            return non_field_errors
        if isinstance(self.errors, dict):
            non_field_errors = [
                NonFieldError(error.message, code=error.code)
                for error in self.errors.pop("field_errors", [])
            ]
            field_errors = [
                FieldError(error["message"], field=field, code=error["code"])
                for field, errors in self.errors.items()
                for error in errors
            ]
            return non_field_errors + field_errors

        raise Exception("Internal error")


class MutationException(Exception):
    """
    Base class for all exceptions raised during mutations.
    """

    def resolve(self):
        raise NotImplementedError

    def __eq__(self, other: Any):
        if not isinstance(other, MutationException):
            return False
        return self.__dict__ == other.__dict__


class GQLException(MutationException):
    """
    A single GQL error (field or non-field)
    """

    def __init__(self, message, code=None, field=None, params=None):
        super().__init__()
        self.message = str(message)
        self.code = code
        self.params = params
        self.field = field
        self.args = (message,)

    def resolve(self) -> List[Union[FieldError, NonFieldError]]:
        return [
            FieldError(
                message=self.message,
                code=self.code,
                field=self.field,
            )
            if self.field
            else NonFieldError(message=self.message, code=self.code)
        ]


class GQLExceptions(MutationException):
    """
    Many GQL errors
    """

    def __init__(self, exceptions: Iterable[MutationException] = None):
        super().__init__()
        self.exceptions = list(exceptions) if exceptions else []

    def add_exception(self, exception: MutationException):
        self.exceptions.append(exception)

    def has_exceptions(self):
        return len(self.exceptions) > 0

    def resolve(self) -> List[Union[FieldError, NonFieldError]]:
        resovled_exceptions = []
        for exception in self.exceptions:
            resovled_exceptions.extend(exception.resolve())
        return resovled_exceptions

    def __bool__(self):
        return self.has_exceptions()

    def __add__(self, other):
        if not isinstance(other, GQLExceptions):
            raise NotImplementedError
        return GQLExceptions(self.exceptions + other.exceptions)

    def __eq__(self, other: Any):
        if not isinstance(other, GQLExceptions):
            raise NotImplementedError
        return self.exceptions == other.exceptions


class PaymentException(GQLException):
    pass


class SquareException(GQLException):
    """An exception with the square API"""

    def __init__(self, square_response):
        passthrough_error_categories = [
            "PAYMENT_METHOD_ERROR",
        ]
        error = (
            square_response.errors[0]
            if square_response.errors and len(square_response.errors)
            else None
        )
        message = (
            (
                error["detail"]
                if error["category"] in passthrough_error_categories
                else "There was an issue processing your payment (%s)" % error["code"]
            )
            if error
            else square_response.reason_phrase
        )

        super().__init__(message, square_response.status_code)


class AuthException(GQLException):
    def __init__(self, message="Authentication Error"):
        super().__init__(message, code=401)


class AuthorizationException(GQLException):
    def __init__(
        self, message="You are not authorized to perform this action", field=None
    ):
        super().__init__(message=message, code=403, field=field)


class ReferencedException(GQLException):
    """
    Thrown when a model can't be deleted because of restricted foreign key
    relations
    """

    def __init__(
        self,
        message="This model cannot be deleted because it is referenced by another",
        field=None,
    ):
        super().__init__(message=message, code="REFERR", field=field)


class FormExceptions(GQLExceptions):
    """
    An exception for handling form errors
    """

    def __init__(self, form_errors: list[ErrorType] = None):
        """
        A form returns a list of error dicts that contains the field name
        and a list of error message. This init method creates a field error for
        each error message.
        """
        exceptions = (
            [
                GQLException(message, field=error.field)
                for error in list(form_errors)
                for message in error.messages
            ]
            if form_errors
            else []
        )
        super().__init__(exceptions)


class NotFoundException(GQLException):
    """An exception for when a resource is not found."""

    def __init__(
        self,
        object_type=None,
        object_id=None,
    ):
        if object_id and object_type:
            error_message = f"Object {object_type} {object_id} not found"
        else:
            error_message = "Object not found"
        super().__init__(message=error_message, code=404)


class SafeMutation(MutationResult, graphene.Mutation):
    """
    Extended graphene.Mutation.
        - Adds errors and success fields
        - Catches any MutationException and formats in errors field
    """

    class Meta:
        abstract = True

    @classmethod
    # pylint: disable=protected-access
    def authorize_request(cls, root, info, **inputs):
        pass

    @classmethod
    def mutate(cls, root, info, **inputs):
        """
        Calls resolve_mutation, catches error and formats
        """
        try:
            cls.authorize_request(root, info, **inputs)
            with transaction.atomic():
                return cls.resolve_mutation(root, info, **inputs)

        except (MutationException, ObjectDoesNotExist) as exception:
            if isinstance(exception, ObjectDoesNotExist):
                exception = NotFoundException()
            # These are our custom exceptions
            return cls(errors=exception.resolve(), success=False)
