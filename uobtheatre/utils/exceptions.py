import graphene
from graphene_django.utils import camelize
from graphene_django.views import GraphQLView
from graphql.error import GraphQLSyntaxError
from graphql.error import format_error as format_graphql_error
from graphql.error.located_error import GraphQLLocatedError
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


class GQLListError(Exception):
    def __init__(self, message=None, errors=[]):
        super().__init__()
        self.message = message
        self.errors = errors


class GQLFieldError(Exception):
    def __init__(self, message, field=None, code=None, params=None):
        super().__init__()
        self.message = str(message)
        self.code = code
        self.params = params
        self.field = field


class CustomErrorType(graphene.Scalar):
    class Meta:
        description = """
    Errors messages and codes mapped to
    fields or non fields errors.
    Example:
    {
        field_name: [
            {
                "message": "error message",
                "code": "error_code"
            }
        ],
        other_field: [
            {
                "message": "error message",
                "code": "error_code"
            }
        ],
        nonFieldErrors: [
            {
                "message": "error message",
                "code": "error_code"
            }
        ]
    }
    """

    @staticmethod
    def serialize(errors):
        raise GQLListError(errors=errors)


def format_field_error(error):
    return {
        error.field: {
            "message": error.message,
            "code": error.code,
        }
    }


def format_list_error(error):
    errors = error.errors
    if isinstance(errors, dict):
        if errors.get("__all__", False):
            errors["non_field_errors"] = errors.pop("__all__")
        return camelize(errors)
    elif isinstance(errors, list):
        return {"nonFieldErrors": errors}
    raise Exception


def format_internal_error(error: Exception):
    return {
        "message": "Internal error",
        "code": 500,
    }


def format_located_error(error):
    if isinstance(error.original_error, GraphQLLocatedError):
        return format_located_error(error.original_error)
    if isinstance(error.original_error, GQLFieldError):
        return format_field_error(error.original_error)
    if isinstance(error.original_error, GQLListError):
        return format_list_error(error.original_error)
    return format_internal_error(error.original_error)


class SafeGraphQLView(GraphQLView):
    @staticmethod
    def format_error(error):
        try:
            if isinstance(error, GraphQLLocatedError):
                return format_located_error(error)
            if isinstance(error, GraphQLSyntaxError):
                return format_graphql_error(error)
            if isinstance(error, GQLListError):
                return format_list_error(error)
        except Exception:
            return format_internal_error(error.original_error)
            print("NO NO NO")
