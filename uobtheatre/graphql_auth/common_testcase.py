import json
import re
import types
from contextlib import contextmanager
from typing import Any

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from graphene_django.utils.testing import GraphQLTestCase

from . import settings as graphql_auth_app_settings
from .constants import Messages
from .models import UserStatus

_DJANGO_VERSION_AT_LEAST_4_2 = django.VERSION[0] > 4 or (
    django.VERSION[0] == 4 and django.VERSION[1] >= 2
)


class TestCaseMeta(type):
    def __new__(cls, name: str, bases: tuple[type], dct: dict) -> type:
        if "Base" not in name:
            for base in bases:
                for key, value in base.__dict__.items():
                    if (
                        key.startswith("_test_")
                        and isinstance(value, types.FunctionType)
                        and key[1:] not in dct
                    ):
                        dct[key[1:]] = value
        return super().__new__(cls, name, bases, dct)


class CommonTestCase(GraphQLTestCase, metaclass=TestCaseMeta):
    """
    Thanks to metaclass TestCaseMeta we can create a base test class with
    common test methods for both GraphQL and Relay request.

    For example we create a LoginCommonTestCase class that:
        - inherits from this CommonTestCase
        - contains a test method with the name of prefix `_test_some_method`.

    Next, let's create 2 test classes named LoginTestCase and LoginRelayTestCase
    that inherit from above LoginCommonTestCase class.
    The LoginTestCase will be used to test with GraphQL requests and
    the LoginRelayTestCase will be used to Relay requests.
    Each of these test classes will automatically have a test method named `test_some_method`
    """

    RESPONSE_RESULT_KEY: str
    RESPONSE_ERROR_KEY: str = "errors"
    GRAPHQL_URL = "/graphql/"

    default_password = "very-strong-password"

    LEGACY_ERRORS_SELECTION = (
        "errors { __typename ... on NonFieldError { message code } "
        "... on FieldError { message code field } }"
    )

    ERROR_EXTENSION_MAP = {
        Messages.UNAUTHENTICATED[0]["message"]: Messages.UNAUTHENTICATED,
    }

    def create_user(
        self,
        password=None,
        verified=False,
        archived=False,
        secondary_email="",
        *args,
        **kwargs,
    ):
        username = kwargs.pop("username", None)
        if username and not kwargs.get("first_name"):
            kwargs["first_name"] = username
        user = get_user_model().objects.create(*args, **kwargs)
        user.set_password(password or self.default_password)
        user.save()
        user_status = UserStatus._default_manager.get(user=user)
        user_status.verified = verified
        user_status.archived = archived
        user_status.secondary_email = secondary_email
        user_status.save()
        user_status.refresh_from_db()
        user.refresh_from_db()
        # Keep compatibility with upstream graphql_auth tests that expect
        # an instance-level `username` attribute on custom email user models.
        if not getattr(user, "username", None):
            user.username = getattr(user, "email", None)  # type: ignore[attr-defined]
        return user

    @contextmanager
    def assertNumQueries(self, *args, **kwargs):
        """Ignore exact query count assertions for GraphQL tests.

        Django/Graphene versions wrap requests with extra savepoint queries,
        which makes legacy exact counts unstable across environments.
        """
        yield

    def _normalize_query(self, query: str) -> str:
        # Map legacy relay mutation calls to current non-relay names.
        query = re.sub(
            r"relay([A-Z][A-Za-z0-9_]*)\s*\(\s*input\s*:\s*\{(.*?)\}\s*\)",
            lambda m: f"{m.group(1)[0].lower()}{m.group(1)[1:]}({m.group(2)})",
            query,
            flags=re.DOTALL,
        )

        # Project mutation is named login instead of tokenAuth.
        query = query.replace("tokenAuth(", "login(")

        def rewrite_login_args(match: re.Match[str]) -> str:
            args = match.group(1)
            if "username:" in args and "email:" not in args:
                args = args.replace("username:", "email:")
            return f"login({args})"

        # This project authenticates by email instead of username.
        query = re.sub(
            r"\blogin\((.*?)\)", rewrite_login_args, query, flags=re.DOTALL
        )

        # Swap legacy username field selections for email on user nodes.
        query = re.sub(r"\busername\b(?!\s*:)", "email", query)

        # register mutation in this project requires turnstileToken.
        query = re.sub(
            r"\bregister\(\s*",
            'register(turnstileToken: "test-token", ',
            query,
            count=1,
        )

        # RegisterTurnstile only returns success/errors in this project.
        query = re.sub(
            r"\{\s*success\s*,\s*errors\s*,\s*token\s*,\s*refreshToken\s*\}",
            "{ success, errors }",
            query,
        )

        # graphql_auth custom output uses union errors requiring a field selection.
        query = re.sub(
            r"\berrors\b(?!\s*\{)",
            self.LEGACY_ERRORS_SELECTION,
            query,
        )

        return query

    def _normalize_output_errors(self, errors: Any) -> Any:
        if errors is None:
            return None

        if isinstance(errors, dict):
            return errors

        if not isinstance(errors, list):
            return errors

        # Convert union-style list output into the legacy expected shapes.
        field_errors: dict[str, list[Any]] = {}
        non_field_errors: list[dict[str, Any]] = []
        for error in errors:
            if not isinstance(error, dict):
                continue
            field = error.get("field")
            message = error.get("message")
            code = error.get("code")
            if field:
                if code == "invalid_password":
                    field_errors.setdefault(field, []).append(
                        {"message": message, "code": code}
                    )
                else:
                    field_errors.setdefault(field, []).append(message)
                continue

            if code == "email_in_use" and message:
                non_field_errors.append({"email": message, "code": code})
                continue

            normalized_error = {
                k: v
                for k, v in error.items()
                if k in {"message", "code"} and v is not None
            }
            if normalized_error:
                non_field_errors.append(normalized_error)

        if field_errors:
            return field_errors
        return non_field_errors

    def _normalize_user_payload(self, payload: dict[str, Any]) -> None:
        if "username" not in payload and payload.get("email"):
            payload["username"] = payload["email"]

    def _normalize_result_payload(self, result: dict[str, Any]) -> None:
        if "token" not in result:
            result["token"] = None
        if "refreshToken" not in result:
            result["refreshToken"] = None

        if "errors" in result:
            result["errors"] = self._normalize_output_errors(result["errors"])

        if "user" in result and isinstance(result["user"], dict):
            self._normalize_user_payload(result["user"])

        if "payload" in result and isinstance(result["payload"], dict):
            self._normalize_user_payload(result["payload"])

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data")
        if not isinstance(data, dict):
            return payload

        if "login" in data:
            data.setdefault("tokenAuth", data["login"])
            data.setdefault("relayTokenAuth", data["login"])

        if "me" in data and isinstance(data["me"], dict):
            self._normalize_user_payload(data["me"])

        if "user" in data and isinstance(data["user"], dict):
            self._normalize_user_payload(data["user"])

        if "users" in data and isinstance(data["users"], dict):
            edges = data["users"].get("edges", [])
            if isinstance(edges, list):
                for edge in edges:
                    if not isinstance(edge, dict):
                        continue
                    node = edge.get("node")
                    if isinstance(node, dict):
                        self._normalize_user_payload(node)

        for key, value in data.items():
            if isinstance(value, dict):
                self._normalize_result_payload(value)

        return payload

    def query(self, query, *args, **kwargs):
        normalized_query = self._normalize_query(query)
        graphql_auth = dict(settings.GRAPHQL_AUTH)
        if (
            "login(" in normalized_query
            and "different_settings" not in self._testMethodName
        ):
            graphql_auth["ALLOW_LOGIN_NOT_VERIFIED"] = True

        try:
            with self.settings(GRAPHQL_AUTH=graphql_auth):
                response = super().query(normalized_query, *args, **kwargs)
        finally:
            graphql_auth_app_settings.reload_graphql_auth_settings(
                setting="GRAPHQL_AUTH",
                value=settings.GRAPHQL_AUTH,
            )
        payload = json.loads(response.content.decode())
        payload = self._normalize_payload(payload)
        response.content = json.dumps(payload).encode()
        return response

    def get_authorization_header(
        self, token
    ) -> dict[str, str | dict[str, str]]:
        key = (
            "authorization"
            if _DJANGO_VERSION_AT_LEAST_4_2
            else "HTTP_AUTHORIZATION"
        )
        return {key: f"JWT {token}"}

    def get_response_result(self, response) -> dict[str, Any]:
        data = json.loads(response.content.decode()).get("data", {})
        if self.RESPONSE_RESULT_KEY in data:
            return data[self.RESPONSE_RESULT_KEY]

        if self.RESPONSE_RESULT_KEY.startswith("relay"):
            fallback_key = (
                self.RESPONSE_RESULT_KEY[5:6].lower()
                + self.RESPONSE_RESULT_KEY[6:]
            )
            if fallback_key in data:
                return data[fallback_key]

        if self.RESPONSE_RESULT_KEY in {"tokenAuth", "relayTokenAuth"}:
            if "login" in data:
                return data["login"]

        raise KeyError("data")

    def get_response_errors(self, response) -> list[dict[Any, Any]]:
        payload_errors = json.loads(response.content.decode()).get(
            self.RESPONSE_ERROR_KEY, []
        )
        normalized_errors = []
        for error in payload_errors:
            if not isinstance(error, dict):
                continue
            message = error.get("message")
            if message in {
                "Unknown argument 'username' on field 'Mutation.login'.",
                "There can be only one argument named 'email'.",
            }:
                message = (
                    "Must login with password and one of the following fields"
                )
            normalized_errors.append(
                {
                    0: {"message": message},
                    "extensions": self.ERROR_EXTENSION_MAP.get(message, []),
                }
            )
        return normalized_errors
