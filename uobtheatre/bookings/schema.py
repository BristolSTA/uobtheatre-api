import itertools

import django_filters
import graphene
from django.db.models import Q
from django_filters import OrderingFilter
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql_relay.node.node import from_global_id

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
from uobtheatre.productions.models import Performance
from uobtheatre.productions.schema import SalesBreakdownNode
from uobtheatre.users.schema import ExtendedUserNode
from uobtheatre.utils.filters import FilterSet


class MiscCostFilter(FilterSet):
    class Meta:
        model = MiscCost
        fields = (
            "id",
            "name",
        )


class MiscCostNode(DjangoObjectType):
    class Meta:
        model = MiscCost
        interfaces = (relay.Node,)
        filterset_class = MiscCostFilter
        fields = (
            "id",
            "name",
            "description",
            "percentage",
            "value",
        )


class TicketNode(DjangoObjectType):
    checked_in = graphene.Boolean()

    def resolve_checked_in_by(self, info):
        if not info.context.user.has_perm(
            "productions.boxoffice",
            self.booking.performance.production,
        ):
            return None
        return self.checked_in_by

    @classmethod
    def get_queryset(cls, queryset, info):
        """Get the queryset for a group of ticket nodes"""
        qs = Q(
            booking__performance__in=Performance.objects.where_can_view_tickets_and_bookings(
                info.context.user
            )
        )
        if info.context.user.is_authenticated:
            qs = qs | Q(booking__user=info.context.user)
        return queryset.filter(qs)

    class Meta:
        model = Ticket
        interfaces = (relay.Node,)


class PriceBreakdownTicketNode(graphene.ObjectType):
    ticket_price = graphene.Int(required=True)
    number = graphene.Int(required=True)
    seat_group = graphene.Field("uobtheatre.venues.schema.SeatGroupNode")
    concession_type = graphene.Field("uobtheatre.discounts.schema.ConcessionTypeNode")
    total_price = graphene.Int(required=True)

    def resolve_total_price(self, _):
        return self.ticket_price * self.number


class PriceBreakdownNode(DjangoObjectType):
    tickets = graphene.List(PriceBreakdownTicketNode)
    tickets_price = graphene.Int(required=True)
    discounts_value = graphene.Int(required=True)
    misc_costs = graphene.List(MiscCostNode)
    subtotal_price = graphene.Int(required=True)
    misc_costs_value = graphene.Int(required=True)
    total_price = graphene.Int(required=True)
    tickets_discounted_price = graphene.Int(required=True)

    def resolve_tickets_price(self, _):
        return self.tickets_price()

    def resolve_discounts_value(self, _):
        return self.discount_value()

    def resolve_subtotal_price(self, _):
        return self.subtotal

    def resolve_total_price(self, _):
        return self.total

    def resolve_tickets_discounted_price(self, _):
        return self.subtotal

    def resolve_tickets(self, _):
        # Group the ticket together, this returns a list of tuples.
        # The first element of the tuple is itself a tuple which contains the
        # seat_group and concession_type, the second element of the typle
        # contains a list of all the elements in that group.
        groups = itertools.groupby(
            self.tickets.order_by("pk"),
            lambda ticket: (ticket.seat_group, ticket.concession_type),
        )

        return [
            PriceBreakdownTicketNode(
                ticket_price=self.performance.price_with_concession(
                    ticket_group[1],
                    self.performance.performance_seat_groups.get(
                        seat_group=ticket_group[0]
                    ),
                ),
                number=len(list(group)),
                seat_group=ticket_group[0],
                concession_type=ticket_group[1],
            )
            for ticket_group, group in groups
        ]

    def resolve_misc_costs(self, _):
        # For some reason the node isnt working for ive had to add all the
        # values in here.
        return [
            MiscCostNode(
                misc_cost,
                name=misc_cost.name,
                description=misc_cost.description,
                value=misc_cost.get_value(self),
                percentage=misc_cost.percentage,
            )
            for misc_cost in MiscCost.objects.all()
        ]

    class Meta:
        model = Booking
        interfaces = (relay.Node,)
        fields = (
            "tickets_price",
            "discounts_value",
            "subtotal_price",
            "misc_costs_value",
            "total_price",
        )


class BookingByMethodOrderingFilter(OrderingFilter):
    """Ordering filter for bookings which adds created at and checked_in

    Extends the default implementation of OrderingFitler to include ordering
    (ascending and descending) of booking orders
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra["choices"] += [
            ("created_at", "Created At"),
            ("-created_at", "Created At (descending)"),
            ("checked_in", "Checked In"),
            ("-checked_in", "Checked In (descending)"),
            ("start", "Start Time"),
            ("-start", "Start Time (descending)"),
        ]

    def filter(self, query_set, value: str):
        """Fitler

        Adds following options:
         - 'created_at'
         - '-created_at' (Descending created at)
         - 'checked_in'
         - '-checked_in' (Descending checked in)
         - 'start'
         - '-start' (Descending start)

        Args:
            query_set (QuerySet): The Queryset which is being filtered.
            value (str): The choices s(eg 'start')

        Returns:
            Queryset: The filtered Queryset
        """

        if value and "checked_in" in value:
            return query_set.annotate_checked_in_proportion().order_by("-proportion")
        if value and "-checked_in" in value:
            return query_set.annotate_checked_in_proportion().order_by("proportion")

        if value and "start" in value:
            return query_set.order_by("performance__start")
        if value and "-start" in value:
            return query_set.order_by("-performance__start")

        # the super class handles the filtering of "created_at"
        return super().filter(query_set, value)


class BookingFilter(FilterSet):
    """Custom filter for BookingNode.

    Restricts BookingNode to only return Bookings owned by the User. Adds
    ordering filter for created_at.

    Also adds filtering for bookings based on the name of its associated
    production.
    """

    status_in = django_filters.MultipleChoiceFilter(
        choices=Booking.Status.choices, field_name="status"
    )

    search = django_filters.CharFilter(method="search_bookings", label="Search")

    production_search = django_filters.CharFilter(
        method="production_search_bookings", label="Production Search"
    )

    production_slug = django_filters.CharFilter(
        method="filter_production_slug", label="Production Slug"
    )

    performance_id = django_filters.CharFilter(
        method="filter_performance_id", label="Performance ID"
    )

    checked_in = django_filters.BooleanFilter(
        method="filter_checked_in", label="Checked In"
    )
    active = django_filters.BooleanFilter(
        method="filter_active", label="Active Bookings"
    )
    expired = django_filters.BooleanFilter(
        method="filter_expired", label="Expired Bookings"
    )
    has_accessibility_info = django_filters.BooleanFilter(
        method="filter_accessibility",
        label="Has Accessibility Info",
    )

    class Meta:
        model = Booking
        fields = "__all__"

    def search_bookings(self, queryset, _, value):
        """
        Given a query string, searches through the bookings using first name,
        last name, email and booking reference.

        Args:
            queryset (Queryset): The bookings queryset.
            value (str): The search query.

        Returns:
            Queryset: Filtered booking queryset.
        """
        query = Q()
        for word in value.split():
            query = (
                query
                | Q(user__first_name__icontains=word)
                | Q(user__last_name__icontains=word)
                | Q(user__email__icontains=word)
                | Q(reference__icontains=word)
            )
        return queryset.filter(query)

    def production_search_bookings(self, queryset, _, value):
        """
        Given a query string, searches through the bookings using the name of each associated production

        Args:
            queryset (Queryset): The bookings queryset.
            value (str): The search query.

        Returns:
            Queryset: Filtered booking queryset.
        """
        query = Q() | Q(performance__production__name__icontains=value)
        return queryset.filter(query)

    def filter_production_slug(self, queryset, _, value):
        """
        Given a query string, searches through the bookings using the slug of
        each associated production. Only return *exact matches*.

        Args:
            queryset (Queryset): The bookings queryset.
            value (str): The search query.

        Returns:
            Queryset: Filtered booking queryset.
        """
        query = Q() | Q(performance__production__slug=value)
        return queryset.filter(query)

    def filter_performance_id(self, queryset, _, value):
        """
        Given a query string - the ID of the performance in base64, searches
        through the bookings using the id of each associated performance.
        Only return *exact matches*.

        Args:
            queryset (Queryset): The bookings queryset.
            value (str): The search query.

        Returns:
            Queryset: Filtered booking queryset.
        """
        query = Q() | Q(performance__id=from_global_id(value)[1])
        return queryset.filter(query)

    def filter_checked_in(self, queryset, _, value):
        return queryset.checked_in(value)

    def filter_active(self, queryset, _, value):
        return queryset.active(value)

    def filter_expired(self, queryset, _, value):
        return queryset.expired(value)

    def filter_accessibility(self, queryset, _, value):
        return queryset.has_accessibility_info(value)

    order_by = BookingByMethodOrderingFilter()


class BookingNode(DjangoObjectType):
    price_breakdown = graphene.Field(PriceBreakdownNode)
    tickets = DjangoListField(TicketNode, required=True)
    user = graphene.Field(ExtendedUserNode, required=True)
    transactions = DjangoFilterConnectionField(
        "uobtheatre.payments.schema.TransactionNode"
    )
    expired = graphene.Boolean(required=True)
    sales_breakdown = graphene.Field(SalesBreakdownNode)

    def resolve_price_breakdown(self, _):
        return self

    def resolve_expired(self, _):
        return self.is_reservation_expired

    @classmethod
    def get_queryset(cls, queryset, info):
        """Get the queryset for a group of booking nodes"""
        qs = Q(
            performance__in=Performance.objects.where_can_view_tickets_and_bookings(
                info.context.user
            )
        )
        if info.context.user.is_authenticated:
            qs = qs | Q(user=info.context.user)
        return queryset.filter(qs)

    class Meta:
        model = Booking
        filterset_class = BookingFilter
        interfaces = (relay.Node,)


class Query(graphene.ObjectType):
    """Query for production module.

    These queries are appended to the main schema Query.
    """

    miscCosts = DjangoFilterConnectionField(MiscCostNode)
    bookings = DjangoFilterConnectionField(BookingNode)
