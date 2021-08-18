"""
Defines base schema for api
"""

import channels
import channels_graphql_ws
import django
import graphene

import uobtheatre.bookings.schema as bookings_schema
import uobtheatre.payments.schema as payments_schema
import uobtheatre.productions.schema as productions_schema
import uobtheatre.societies.schema as societies_schema
import uobtheatre.users.schema as users_schema
import uobtheatre.venues.schema as venues_schema


class MySubscription(channels_graphql_ws.Subscription):
    """Simple GraphQL subscription."""

    # Subscription payload.
    event = graphene.String()

    class Arguments:
        """That is how subscription arguments are defined."""

        arg1 = graphene.String()
        arg2 = graphene.String()

    @staticmethod
    def subscribe(payload, _, arg1, arg2):
        """Called when user subscribes."""
        print(payload)
        print(arg1)
        print(arg2)

        # Return the list of subscription group names.
        return ["group42"]

    @staticmethod
    def publish(payload, _, arg1, arg2):
        """Called to notify the client."""
        print(payload)
        print(arg1)
        print(arg2)

        # Here `payload` contains the `payload` from the `broadcast()`
        # invocation (see below). You can return `MySubscription.SKIP`
        # if you wish to suppress the notification to a particular
        # client. For example, this allows to avoid notifications for
        # the actions made by this particular client.

        return MySubscription(event="Something has happened!")


class Query(
    venues_schema.Query,
    productions_schema.Query,
    societies_schema.Query,
    users_schema.Query,
    bookings_schema.Query,
    payments_schema.Query,
    graphene.ObjectType,
):
    """
    Defines base Query for api
    """


class Mutation(
    users_schema.Mutation,
    bookings_schema.Mutation,
    graphene.ObjectType,
):
    """
    Defines base Mutation for api
    """


class Subscription(graphene.ObjectType):
    """Root GraphQL subscription."""

    my_subscription = MySubscription.Field()


schema = graphene.Schema(query=Query, mutation=Mutation, subscription=Subscription)


class WebsocketConsumer(channels_graphql_ws.GraphqlWsConsumer):
    """Channels WebSocket consumer which provides GraphQL API."""

    schema = schema

    # Uncomment to send keepalive message every 42 seconds.
    # send_keepalive_every = 42

    # Uncomment to process requests sequentially (useful for tests).
    # strict_ordering = True

    async def on_connect(self, _):
        """New client connection handler."""
        print("New client connected! Broadcasting")


application = channels.routing.ProtocolTypeRouter(
    {
        "websocket": channels.routing.URLRouter(
            [
                django.urls.path("graphql/", WebsocketConsumer.as_asgi()),
            ]
        )
    }
)
