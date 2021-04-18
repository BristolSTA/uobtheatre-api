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


from typing import List, Union

import graphene
from django.db import transaction


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


class GQLFieldException(MutationException):
    """
    A single GQL Field error
    """

    def __init__(self, message, field=None, code=None, params=None):
        super().__init__()
        self.message = str(message)
        self.code = code
        self.params = params
        self.field = field

    def resolve(self) -> List[Union[FieldError, NonFieldError]]:
        return [FieldError(message=self.message, code=self.code, field=self.field)]


class GQLNonFieldException(MutationException):
    """
    A single GQL Field error
    """

    def __init__(self, message, code=None):
        super().__init__()
        self.message = str(message)
        self.code = code

    def resolve(self) -> List[Union[FieldError, NonFieldError]]:
        return [NonFieldError(message=self.message, code=self.code)]


class SquareException(GQLNonFieldException):
    def __init__(self, square_response):
        super().__init__(square_response.reason_phrase, square_response.status_code)


class AuthException(GQLNonFieldException):
    def __init__(self, message="Authentication Error"):
        super().__init__(message, code=401)


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
                return cls.resolve_mutation(root, info, **inputs)

        except MutationException as exception:
            # These are our custom exceptions
            return cls(errors=exception.resolve(), success=False)
