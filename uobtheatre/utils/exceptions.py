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
    # full_details = exception.get_full_details()
    # custom_response_data["full_details"] = full_details

    # checks if the raised exception is of the type you want to handle
    # if isinstance(exc, ConnectionError):
    #     # defines custom response data
    #     err_data = {"MSG_HEADER": "some custom error messaging"}

    # #     # logs detail data from the exception being handled
    # #     logging.error(f"Original error detail and callstack: {exc}")
    # #     # returns a JsonResponse
    # #     return JsonResponse(err_data, safe=False, status=503)

    response.data = custom_response_data
    return response
    # return JsonResponse(custom_response_data, safe=False, status=custom_response_status)
