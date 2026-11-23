from typing import Callable

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.utils.module_loading import import_string

from uobtheatre.utils.utils import get_by_email

from .settings import graphql_auth_settings as app_settings
from .types import ExpectedErrorType


def get_user_by_email(email):
    """
    get user by email or by secondary email, ignoring case
    raise ObjectDoesNotExist
    """

    UserModel = get_user_model()

    user = get_by_email(
        UserModel._default_manager.select_related("status"),
        email,
        [UserModel.EMAIL_FIELD, "status__secondary_email"],  # type: ignore
    )
    if user is None:
        raise ObjectDoesNotExist
    return user


def get_user_to_login(**kwargs):
    """
    get user by kwargs or secondary email
    to perform login
    raise ObjectDoesNotExist
    """

    UserModel = get_user_model()

    if "email" in kwargs.keys():
        email_fields = ["email"]
        if app_settings.ALLOW_LOGIN_WITH_SECONDARY_EMAIL:
            email_fields.append("status__secondary_email")
        user = get_by_email(
            UserModel._default_manager.select_related("status"),
            kwargs["email"],
            email_fields,
        )
    else:
        user = (
            UserModel._default_manager.select_related("status")
            .filter(**kwargs)
            .first()
        )
    if user:
        return user
    else:
        raise ObjectDoesNotExist


def get_async_email_func() -> Callable | None:
    if app_settings.is_async_email:
        return import_string(app_settings.EMAIL_ASYNC_TASK)
    return None


async_email_func = get_async_email_func()


def get_output_error_type():
    if app_settings.CUSTOM_ERROR_TYPE and isinstance(
        app_settings.CUSTOM_ERROR_TYPE, str
    ):
        return import_string(app_settings.CUSTOM_ERROR_TYPE)
    else:
        return ExpectedErrorType


OutputErrorType = get_output_error_type()
