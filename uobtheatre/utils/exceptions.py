import graphene
from graphene_django.constants import MUTATION_ERRORS_FLAG
from graphene_django.utils.utils import set_rollback
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


class GQLAuthError(Exception):
    def __init__(self, errors):
        super().__init__()
        self.errors = errors


class GQLListError(Exception):
    """
    List or Dict of GQL errors
    """

    def __init__(self, message=None, field_errors=[], non_field_errors=[]):
        super().__init__()
        self.message = message
        self.field_errors = field_errors
        self.non_field_errors = non_field_errors


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

# https://gist.github.com/smmoosavi/033deffe834e6417ed6bb55188a05c88


class GQLFieldError(Exception):
    """
    A single GQL Field error
    """

    def __init__(self, message, field=None, code=None):
        super().__init__()
        self.message = str(message)
        self.code = code
        self.field = field


class GQLNonFieldError(Exception):
    """
    A single GQL Field error
    """

    def __init__(self, message, code=None):
        super().__init__()
        self.message = str(message)
        self.code = code


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
        # TODO Create GQLListError with a list of error or FieldErrors and Non field erorr
        # Raise gqlautherror maybe so we can handle customly
        if isinstance(errors, dict):
            print(errors)
            non_field_errors = [
                GQLNonFieldError(error.message, code=error.code)
                for error in errors.pop("__all__", [])
            ]
            field_errors = [
                GQLFieldError(value[0]["message"], field=key)
                for key, value in errors.items()
            ]
            raise GQLListError(
                non_field_errors=non_field_errors, field_errors=field_errors
            )

        elif isinstance(errors, list):
            raise GQLListError(
                non_field_errors=[
                    GQLNonFieldError(message=error.message, code=error.code)
                    for error in errors
                ]
            )
        raise Exception


def format_field_error(error):
    print("Formatting field error")
    return {
        "message": error.message,
        "code": error.code,
        "field": error.field,
    }


def format_non_field_error(error):
    return {
        "message": error.message,
        "code": error.code,
    }


def format_list_error(error: GQLListError):
    return [format_field_error(err) for err in error.field_errors] + [
        format_non_field_error(err) for err in error.non_field_errors
    ]


def format_internal_error(error: Exception):
    return {
        "message": "Internal error",
        "code": 500,
    }


def format_located_error(error):
    print("Formatting")
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
        print("In format error")
        try:
            if isinstance(error, GraphQLLocatedError):
                return format_located_error(error)
            if isinstance(error, GraphQLSyntaxError):
                return format_graphql_error(error)
            if isinstance(error, GQLListError):
                return format_list_error(error)
        except Exception:
            return format_internal_error(error.original_error)

    def get_response(self, request, data, show_graphiql=False):

        query, variables, operation_name, id = self.get_graphql_params(request, data)

        execution_result = self.execute_graphql_request(
            request, data, query, variables, operation_name, show_graphiql
        )

        if getattr(request, MUTATION_ERRORS_FLAG, False) is True:
            set_rollback()

        status_code = 200
        if execution_result:
            response = {}

            if execution_result.errors:
                set_rollback()
                response["errors"] = [
                    self.format_error(e) for e in execution_result.errors
                ]
                new_errors = []
                for error in response["errors"]:
                    if isinstance(error, list):
                        new_errors.extend(error)
                    else:
                        new_errors.append(error)
                response["errors"] = new_errors

            if execution_result.invalid:
                status_code = 400
            else:
                response["data"] = execution_result.data

            if self.batch:
                response["id"] = id
                response["status"] = status_code

            result = self.json_encode(request, response, pretty=show_graphiql)
        else:
            result = None

        return result, status_code
