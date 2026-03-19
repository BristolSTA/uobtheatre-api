from copy import copy

from django.conf import settings as django_settings
from django.test import TestCase

from uobtheatre.graphql_auth import settings


class AppSettingsTestCase(TestCase):
    def test_reload_settings(self):
        default_allow_login_not_verified = django_settings.GRAPHQL_AUTH[
            "ALLOW_LOGIN_NOT_VERIFIED"
        ]
        self.assertEqual(
            settings.graphql_auth_settings.ALLOW_LOGIN_NOT_VERIFIED,
            default_allow_login_not_verified,
        )

        graphql_auth = copy(django_settings.GRAPHQL_AUTH)
        graphql_auth.update({"ALLOW_LOGIN_NOT_VERIFIED": False})
        settings.reload_graphql_auth_settings(
            setting="GRAPHQL_AUTH", value=graphql_auth
        )
        self.assertFalse(
            settings.graphql_auth_settings.ALLOW_LOGIN_NOT_VERIFIED
        )

        # back to the primary settings
        graphql_auth.update(
            {"ALLOW_LOGIN_NOT_VERIFIED": default_allow_login_not_verified}
        )
        settings.reload_graphql_auth_settings(
            setting="GRAPHQL_AUTH", value=graphql_auth
        )
        self.assertEqual(
            settings.graphql_auth_settings.ALLOW_LOGIN_NOT_VERIFIED,
            default_allow_login_not_verified,
        )
