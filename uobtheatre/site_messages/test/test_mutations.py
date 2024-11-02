# pylint: disable=too-many-lines
from datetime import datetime
from unittest.mock import patch

import pytest
import pytz
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.site_messages.models import Message
from uobtheatre.users.test.factories import UserFactory

###
# Production Mutations
###


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [True, False])
def test_site_message_mutation_create(gql_client, with_permission):
    user = UserFactory()
    gql_client.user = user

    request = """
        mutation {
          siteMessage(
            input: {
                message: "Test Alert"
                active: true
                displayStart: "2021-11-09T00:00:00"
                eventStart: "2021-11-10T00:00:00"
                eventEnd: "2021-11-11T00:00:00"
                type: "ALERT"
                creator: "%s"
             }
          ) {
            success
            errors {
                ... on FieldError {
                    field
                    message
                }
                ... on NonFieldError {
                    message
                }
            }
            siteMessage {
                message
                active
            }
         }
        }
    """ % (
        gql_client.user.id,
    )
    if with_permission:
        assign_perm("site_messages.add_message", gql_client.user)

    response = gql_client.execute(request)
    print(response)
    assert response["data"]["siteMessage"]["success"] is with_permission

    if with_permission:
        assert response["data"]["siteMessage"]["siteMessage"] == {
            "message": "Test Alert",
            "active": True,
        }
        assert Message.objects.count() == 1