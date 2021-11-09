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
from typing import List, Union

import graphene
from django.db import transaction
from graphene.utils.str_converters import to_camel_case


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
    message = graphene.String()
    field = graphene.String()
    code = graphene.String()


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
    def resolve(self):
        raise NotImplementedError


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

    def resolve(self) -> List[Union[FieldError, NonFieldError]]:
        return [
            FieldError(
                message=self.message, code=self.code, field=to_camel_case(self.field)
            )
            if self.field
            else NonFieldError(message=self.message, code=self.code)
        ]


class GQLExceptions(MutationException):
    """
    Many GQL errors
    """

    def __init__(self, exceptions: List[MutationException] = None):
        super().__init__()
        self.exceptions = exceptions or []

    def add_exception(self, exception: MutationException):
        self.exceptions.append(exception)

    def has_exceptions(self):
        return len(self.exceptions) > 0

    def resolve(self) -> List[Union[FieldError, NonFieldError]]:
        resovled_exceptions = []
        for exception in self.exceptions:
            resovled_exceptions.extend(exception.resolve())
        return resovled_exceptions


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
    """Thrown when a model can't be deleted because of restricted foreign key relations"""

    def __init__(
        self,
        message="This model cannot be deleted because it is referenced by another",
        field=None,
    ):
        super().__init__(message=message, code="REFERR", field=field)


class SafeMutation(MutationResult, graphene.Mutation):
    """
    Extended graphene.Mutation.
        - Adds errors and success fields
        - Catches any MutationException and formats in errors field
    """

    class Meta:
        abstract = True

    @classmethod
    def mutate(cls, root, info, **inputs):
        """
        Calls resolve_mutation, catches error and formats
        """
        try:
            with transaction.atomic():
                try:
                    return cls.resolve_mutation(root, info, **inputs)
                except AttributeError as error:
                    if not str(error).endswith("'resolve_mutation'"):
                        raise error
                    return super().mutate(root, info, **inputs)

        except MutationException as exception:
            # These are our custom exceptions
            return cls(errors=exception.resolve(), success=False)
