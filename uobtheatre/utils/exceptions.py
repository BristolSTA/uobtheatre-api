from typing import List, Union

import graphene
from django.db import transaction

# https://gist.github.com/smmoosavi/033deffe834e6417ed6bb55188a05c88
# TODO We should probably raise these error instead and then format for you in
# the mutation, ie in mutation mixin wrap the mutation funciton in a try and
# handle errors there


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
            return

        if isinstance(self.errors, list):
            non_field_errors = [
                NonFieldError(error["message"], code=error["code"])
                for error in self.errors
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
    pass


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


class SafeMutation(MutationResult, graphene.Mutation):
    class Meta:
        abstract = True

    @classmethod
    def mutate(cls, root, info, **input):
        try:
            with transaction.atomic():
                return cls.resolve_mutation(root, info, **input)

        except Exception as exception:
            # These are our custom exceptions
            if isinstance(exception, MutationException):
                return cls(errors=exception.resolve(), success=False)

            raise exception
