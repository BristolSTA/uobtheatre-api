import datetime

import pytest
from django.utils import timezone
from graphql_relay.node.node import to_global_id

from uobtheatre.site_messages.test.factories import (
    SiteMessageFactory,
    create_site_message,
)


@pytest.mark.django_db
def test_site_message_schema(gql_client):
    messages = [SiteMessageFactory() for i in range(3)]

    response = gql_client.execute(
        """
        {
          siteMessages {
            edges {
              node {
                id
                message
                active
                indefiniteOverride
                displayStart
                eventStart
                eventEnd
                type
                creator {
                  id
                }
                dismissalPolicy
                eventDuration
                toDisplay
              }
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "siteMessages": {
                "edges": [
                    {
                        "node": {
                            "id": to_global_id("SiteMessageNode", message.id),
                            "message": message.message,
                            "active": message.active,
                            "indefiniteOverride": message.indefinite_override,
                            "displayStart": message.display_start.isoformat(),
                            "eventStart": message.event_start.isoformat(),
                            "eventEnd": message.event_end.isoformat(),
                            "type": message.type,
                            "creator": {
                                "id": to_global_id("UserNode", message.creator.id)
                            },
                            "dismissalPolicy": message.dismissal_policy,
                            "eventDuration": int(
                                message.duration.total_seconds() // 60
                            ),
                            "toDisplay": message.to_display,
                        }
                    }
                    for index, message in enumerate(messages)
                ]
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query_args, expected_message",
    [
        (f'id: "{to_global_id("SiteMessageNode", 1)}"', 1),
        (f'id: "{to_global_id("SiteMessageNode", 2)}"', 2),
        (f'id: "{to_global_id("SiteMessageNode", 3)}"', None),
    ],
)
def test_resolve_site_message(gql_client, query_args, expected_message):
    SiteMessageFactory(id=1)
    SiteMessageFactory(id=2)

    request = """
      query {
	      siteMessage%s {
          id
        }
      }
    """
    response = gql_client.execute(request % (f"({query_args})" if query_args else ""))

    if expected_message is not None:
        assert response["data"]["siteMessage"]["id"] == to_global_id(
            "SiteMessageNode", expected_message
        )
    else:
        assert response["data"]["siteMessage"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "factories, requests",
    [
        # active exact tests
        (
            [
                (SiteMessageFactory, {"active": True}),
                (SiteMessageFactory, {"active": True}),
                (SiteMessageFactory, {"active": False}),
            ],
            [("active: true", 2), ("active: false", 1)],
        ),
        # type exact test
        (
            [
                (SiteMessageFactory, {"type": "INFORMATION"}),
                (SiteMessageFactory, {"type": "INFORMATION"}),
                (SiteMessageFactory, {"type": "ALERT"}),
            ],
            [
                ('type: "INFORMATION"', 2),
                ('type: "ALERT"', 1),
                ('type: "MAINTENANCE"', 0),
            ],
        ),
    ],
)
def test_site_message_filter(factories, requests, gql_client):
    # Create all the objects with the factories
    for fact in factories:
        factory, args = fact
        factory(**args)

    # Test all the requests return the correct number
    for request in requests:
        filter_args, expected_number = request

        query_string = "{ siteMessages(" + filter_args + ") { edges { node { id } } } }"
        response = gql_client.execute(query_string)

        assert len(response["data"]["siteMessages"]["edges"]) == expected_number


@pytest.mark.django_db
@pytest.mark.parametrize(
    "order_by, expected_order",
    [
        ("display_start", [0, 1, 2, 3]),
        ("-display_start", [3, 2, 1, 0]),
        ("start", [0, 2, 3, 1]),
        ("-start", [1, 3, 2, 0]),
        ("end", [3, 0, 2, 1]),
        ("-end", [1, 2, 0, 3]),
    ],
)
def test_site_message_orderby(order_by, expected_order, gql_client):
    current_time = timezone.now()

    messages = [
        create_site_message(
            display_start=current_time + datetime.timedelta(days=1),
            event_start=current_time + datetime.timedelta(days=3),
            event_end=current_time + datetime.timedelta(days=7),
            id=0,
        ),
        create_site_message(
            display_start=current_time + datetime.timedelta(days=2),
            event_start=current_time + datetime.timedelta(days=6),
            event_end=current_time + datetime.timedelta(days=9),
            id=1,
        ),
        create_site_message(
            display_start=current_time + datetime.timedelta(days=3),
            event_start=current_time + datetime.timedelta(days=4),
            event_end=current_time + datetime.timedelta(days=8),
            id=2,
        ),
        create_site_message(
            display_start=current_time + datetime.timedelta(days=4),
            event_start=current_time + datetime.timedelta(days=5),
            event_end=current_time + datetime.timedelta(days=5),
            id=3,
        ),
    ]
    request = """
        {
          siteMessages(orderBy: "%s") {
            edges {
              node {
                id
              }
            }
          }
        }
        """

    response = gql_client.execute(request % order_by)

    assert response["data"]["siteMessages"]["edges"] == [
        {"node": {"id": to_global_id("SiteMessageNode", messages[i].id)}}
        for i in expected_order
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_name, value_days, expected_outputs",
    [
        ("displayStart_Gte", 3, [3, 2]),
        ("displayStart_Lte", 3, [0, 2, 1]),
        ("start_Gte", 4, [3, 2, 1]),
        ("start_Lte", 4, [0, 2]),
        ("end_Gte", 6, [0, 2, 1]),
        ("end_Lte", 6, [3]),
    ],
)
def test_site_message_time_filters(
    filter_name, value_days, expected_outputs, gql_client
):
    current_time = timezone.now().replace(microsecond=0, second=0)

    messages = [
        create_site_message(
            display_start=current_time + datetime.timedelta(days=1),
            event_start=current_time + datetime.timedelta(days=3),
            event_end=current_time + datetime.timedelta(days=7),
            id=0,
        ),
        create_site_message(
            display_start=current_time + datetime.timedelta(days=2),
            event_start=current_time + datetime.timedelta(days=6),
            event_end=current_time + datetime.timedelta(days=9),
            id=1,
        ),
        create_site_message(
            display_start=current_time + datetime.timedelta(days=3),
            event_start=current_time + datetime.timedelta(days=4),
            event_end=current_time + datetime.timedelta(days=8),
            id=2,
        ),
        create_site_message(
            display_start=current_time + datetime.timedelta(days=4),
            event_start=current_time + datetime.timedelta(days=5),
            event_end=current_time + datetime.timedelta(days=5),
            id=3,
        ),
    ]
    # Check we get 6 of the upcoming messages back in the right order
    request = """
        {
          siteMessages(%s: "%s", orderBy: "end") {
            edges {
              node {
                id
              }
            }
          }
        }
        """

    response = gql_client.execute(
        request
        % (
            filter_name,
            (current_time + datetime.timedelta(days=value_days)).isoformat(),
        )
    )

    assert response["data"]["siteMessages"]["edges"] == [
        {"node": {"id": to_global_id("SiteMessageNode", messages[i].id)}}
        for i in expected_outputs
    ]
