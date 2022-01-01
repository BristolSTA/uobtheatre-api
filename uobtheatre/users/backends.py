from typing import TYPE_CHECKING, Optional

from graphql_jwt.exceptions import JSONWebTokenError
from graphql_jwt.shortcuts import get_user_by_token
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

if TYPE_CHECKING:
    from uobtheatre.users.models import User


class GraphqlJWTAuthentication(authentication.BaseAuthentication):
    """
    Authentication class for handling auth in django rest framework (drf)
    views. This uses the same headers as the GraphQL API to authenticate the
    user. The supplied header is "Authorization: JWT <token>" and drf will
    parse this as "HTTP_AUTHORIZATION: JWT <token>" in the META of the request.
    """

    def authenticate(self, request) -> Optional[tuple["User", None]]:
        """
        Given the request authenticate the user.

        Args:
            request (HttpRequest): The request object.

        Returns:
            Tuple[User, None]: The authenticated user and the auth attribute of the
                request. Im not sure what the auth is for so its always None.
                If auth is not attempted then None is returned.

        Raises:
            AuthenticationFailed: If the auth fails.
        """
        if request.META.get("HTTP_AUTHORIZATION", None) is None:
            return None

        try:
            token = request.META.get("HTTP_AUTHORIZATION").split()[1]
        except (IndexError, AttributeError) as exc:
            raise AuthenticationFailed("Invalid token") from exc

        try:
            user = get_user_by_token(token, request)
        except JSONWebTokenError as exc:
            raise AuthenticationFailed("JWT invalid or expired") from exc

        if user is None:
            raise AuthenticationFailed("User not found")

        return user, None
