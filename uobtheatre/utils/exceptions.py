import graphene
from rest_framework.serializers import ValidationError
from rest_framework.views import exception_handler

from config.settings.common import FIELD_ERRORS_KEY, NON_FIELD_ERRORS_KEY


def custom_exception_handler(exception, context):
    # Call REST framework's default exception handler first
    response = exception_handler(exception, context)

    custom_response_data = {}

    if isinstance(exception, ValidationError):
        custom_response_data["errors"] = {}
        custom_response_data["errors"][FIELD_ERRORS_KEY] = []
        custom_response_data["errors"][NON_FIELD_ERRORS_KEY] = []

        for key, item in exception.detail.serializer._errors.items():
            if key == "non_field_errors":
                custom_response_data["errors"][NON_FIELD_ERRORS_KEY] = item
            else:
                custom_response_data["errors"][FIELD_ERRORS_KEY].append({key: item})

    elif not response:
        return None

    elif isinstance(response.data, list):
        custom_response_data["errors"] = response.data

    else:
        custom_response_data["errors"] = [response.data]

    # Add status_code and error_type to exception
    custom_response_data["status_code"] = response.status_code
    custom_response_data["error_type"] = exception.__class__.__name__

    # Adds full error details obj to response
    # full_details = exception.get_full_details()
    # custom_response_data["full_details"] = full_details

    response.data = custom_response_data
    return response


# https://gist.github.com/smmoosavi/033deffe834e6417ed6bb55188a05c88
# TODO We should probably raise these error instead and then format for you in the mutation, ie in mutation mixin wrap the mutation funciton in a try and handle errors there
# class GQLFieldError(Exception):
#     """
#     A single GQL Field error
#     """
#
#     def __init__(self, message, field=None, code=None, params=None):
#         super().__init__()
#         self.message = str(message)
#         self.code = code
#         self.params = params
#         self.field = field
# class GQLNonFieldError(Exception):
#     """
#     A single GQL Field error
#     """
#
#     def __init__(self, message, code=None):
#         super().__init__()
#         self.message = str(message)
#         self.code = code


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
        non_field_errors = [
            NonFieldError(error.message, code=error.code)
            for error in self.errors.pop("__all__", [])
        ]
        field_errors = [
            FieldError(error["message"], field=field, code=error["code"])
            for field, errors in self.errors.items()
            for error in errors
        ]
        return non_field_errors + field_errors
