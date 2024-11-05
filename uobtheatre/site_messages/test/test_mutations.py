# pylint: disable=too-many-lines
from datetime import datetime
from unittest.mock import patch

import pytest
import pytz
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.site_messages.models import Message
from uobtheatre.site_messages.test.factories import SiteMessageFactory
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
             }
          ) {
            success
            message {
                message
                active
            }
         }
        }
    """
    if with_permission:
        assign_perm("site_messages.add_message", gql_client.user)

    response = gql_client.execute(request)

    assert response["data"]["siteMessage"]["success"] is with_permission

    if with_permission:
        assert response["data"]["siteMessage"]["message"] == {
            "message": "Test Alert",
            "active": True,
        }
        assert Message.objects.count() == 1

@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [True, False])
def test_update_site_message(gql_client, with_permission):
    user = UserFactory()
    gql_client.user = user

    message = SiteMessageFactory(
        message="Test Alert",
        active=True,
        display_start=datetime(2021, 11, 9, tzinfo=pytz.utc),
        event_start=datetime(2021, 11, 10, tzinfo=pytz.utc),
        event_end=datetime(2021, 11, 11, tzinfo=pytz.utc),
        type=Message.Type.ALERT,
    )

    request = """
        mutation {
          siteMessage(
            input: {
                id: "%s"
                message: "Test Alert 2"
                active: false
                displayStart: "2021-11-09T00:00:00"
                eventStart: "2021-11-10T00:00:00"
                eventEnd: "2021-11-11T00:00:00"
                type: "INFORMATION"
             }
          ) {
            success
            message {
                message
                active
            }
         }
        }
    """ % (to_global_id("SiteMessageNode", message.id))

    if with_permission:
        assign_perm("site_messages.change_message", gql_client.user)

    response = gql_client.execute(request)

    assert response["data"]["siteMessage"]["success"] is with_permission

    if with_permission:
        assert response["data"]["siteMessage"]["message"] == {
            "message": "Test Alert 2",
            "active": False,
        }
        assert Message.objects.count() == 1