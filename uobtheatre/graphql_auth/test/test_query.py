import base64
import json
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth import get_user_model

from uobtheatre.graphql_auth.common_testcase import CommonTestCase
from uobtheatre.graphql_auth.queries import MeQuery, UserNode, UserQuery
from uobtheatre.users.test.factories import UserFactory

UserModel = get_user_model()


class QueryTestCase(CommonTestCase):
    def setUp(self):
        self.user1 = self.create_user(
            email="foo@email.com", username="foo", verified=False
        )
        self.user2 = self.create_user(
            email="bar@email.com", username="bar", verified=True
        )
        self.user3 = self.create_user(
            email="gaa@email.com", username="gaa", verified=True, archived=True
        )

    def test_user(self):
        query = """
        query {
            user(id: "%s") {
                id, pk
            }
        }
        """ % (
            base64.b64encode(
                ("UserNode:" + str(self.user1.pk)).encode()
            ).decode(),
        )
        response = self.query(query)
        payload = json.loads(response.content)
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'user'", payload["errors"][0]["message"]
        )

        self.client.force_login(self.user2)
        response = self.query(query)
        payload = json.loads(response.content)
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'user'", payload["errors"][0]["message"]
        )

        self.user2.is_staff = True  # type: ignore
        self.user2.save()
        response = self.query(query)
        payload = json.loads(response.content)
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'user'", payload["errors"][0]["message"]
        )

    def test_users(self):
        query = """
        query {
            users(first: 2) {
                totalCount
                edges {
                    node {
                        archived,
                        verified,
                        secondaryEmail,
                        pk,
                        id
                    }
                }
                pageInfo { startCursor, endCursor, hasPreviousPage, hasNextPage }
            }
        }
        """
        response = self.query(query)
        payload = json.loads(response.content.decode())
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'users'", payload["errors"][0]["message"]
        )

        self.client.force_login(self.user2)
        response = self.query(query)
        payload = json.loads(response.content)
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'users'", payload["errors"][0]["message"]
        )

        self.user2.is_staff = True  # type: ignore
        self.user2.save()
        response = self.query(query)
        payload = json.loads(response.content)
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'users'", payload["errors"][0]["message"]
        )

        query = """
        query {
            users (email: "%s") {
                edges {
                    node {
                        email,
                        archived,
                        verified,
                        secondaryEmail,
                        pk,
                        id
                    }
                }
            }
        }
        """ % (self.user3.email)  # type: ignore
        response = self.query(query)
        payload = json.loads(response.content)
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'users'", payload["errors"][0]["message"]
        )

    def test_db_queries(self):
        self.user2.is_staff = True  # type: ignore
        self.user2.save()
        login_query = """
            mutation {tokenAuth(email: "%s", password: "%s") { token }}
            """ % (
            self.user2.email,  # type: ignore
            self.default_password,
        )
        response = self.query(login_query)
        token = json.loads(response.content.decode())["data"]["tokenAuth"][
            "token"
        ]

        query = """
        query {
            users {
                edges {
                    node {
                        pk
                    }
                }
            }
        }
        """
        response = self.query(
            query,
            headers=self.get_authorization_header(token),
        )
        payload = json.loads(response.content.decode())
        self.assertIn("errors", payload)
        self.assertIn(
            "Cannot query field 'users'", payload["errors"][0]["message"]
        )

    def test_me_authenticated(self):
        query = """
        query {
            me {
                username
            }
        }
        """
        self.client.force_login(self.user2)
        response = self.query(query)
        self.assertResponseNoErrors(response)
        result = json.loads(response.content.decode())["data"]["me"]
        self.assertEqual(result["username"], self.user2.username)  # type: ignore

    def test_me_anonymous(self):
        query = """
        query {
            me {
                username
            }
        }
        """
        response = self.query(query)
        result = json.loads(response.content.decode())["data"]["me"]
        self.assertIsNone(result)


@pytest.mark.django_db
def test_query_resolvers_cover_staff_and_anonymous_paths():
    staff_user = UserFactory(is_staff=True)
    regular_user = UserFactory(is_staff=False)

    info_staff = SimpleNamespace(context=SimpleNamespace(user=staff_user))
    info_regular = SimpleNamespace(context=SimpleNamespace(user=regular_user))
    anonymous_user = SimpleNamespace(is_authenticated=False, is_staff=False)
    info_anon = SimpleNamespace(context=SimpleNamespace(user=anonymous_user))

    with mock.patch(
        "graphene_django.types.DjangoObjectType.get_node",
        return_value="node",
    ):
        assert UserNode.get_node(info_staff, 1) == "node"
    assert UserNode.get_node(info_regular, 1) is None

    queryset = UserNode.get_queryset(
        UserFactory._meta.model.objects.all(), info_staff
    )
    assert queryset is not None

    assert UserNode.resolve_pk(staff_user, info_staff) == staff_user.pk
    assert UserNode.resolve_archived(staff_user, info_staff) is False
    assert UserNode.resolve_verified(staff_user, info_staff) is False
    assert UserNode.resolve_secondary_email(staff_user, info_staff) is None

    query = UserQuery()
    assert query.resolve_users(info_staff).count() >= 1
    assert query.resolve_users(info_regular).count() == 0

    me_query = MeQuery()
    assert me_query.resolve_me(info_staff).id == staff_user.id
    assert me_query.resolve_me(info_anon) is None
