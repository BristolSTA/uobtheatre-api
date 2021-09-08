import django_filters
import graphene
from graphene import relay
from graphene_django import DjangoListField
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.discounts.schema import ConcessionTypeNode, DiscountNode
from uobtheatre.productions.models import (
    AudienceWarning,
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionTeamMember,
)
from uobtheatre.users.abilities import PermissionsMixin
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import DjangoObjectType, GrapheneEnumMixin


class CrewRoleNode(GrapheneEnumMixin, DjangoObjectType):
    class Meta:
        model = CrewRole
        interfaces = (relay.Node,)


class CastMemberNode(DjangoObjectType):
    class Meta:
        model = CastMember
        interfaces = (relay.Node,)


class ProductionTeamMemberNode(DjangoObjectType):
    class Meta:
        model = ProductionTeamMember
        interfaces = (relay.Node,)


class CrewMemberNode(DjangoObjectType):
    class Meta:
        model = CrewMember
        interfaces = (relay.Node,)


class WarningNode(DjangoObjectType):
    class Meta:
        model = AudienceWarning
        interfaces = (relay.Node,)


class ProductionByMethodOrderingFilter(django_filters.OrderingFilter):
    """Ordering filter for productions which adds start and end.

    Extends the default implementation of OrderingFitler to include ordering
    (ascending and descending) of production start and end time.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra["choices"] += [
            ("start", "Start"),
            ("-start", "Start (descending)"),
            ("end", "End"),
            ("-end", "End (descending)"),
        ]

    def filter(self, query_set, value: str):
        """Fitler for start and end of production

        Adds following options:
         - 'start'
         - '-start' (Descending start)
         - 'end'
         - '-end' (Descending end)

        Args:
            query_set (QuerySet): The Queryset which is being filtered.
            value (str): The choices s(eg 'start')

        Returns:
            Queryset: The filtered Queryset
        """
        if value and "start" in value:
            return query_set.annotate_start().order_by("start")
        if value and "-start" in value:
            return query_set.annotate_start().order_by("-start")

        if value and "end" in value:
            return query_set.annotate_end().order_by("end")
        if value and "-end" in value:
            return query_set.annotate_end().order_by("-end")

        return super().filter(query_set, value)


class ProductionFilter(FilterSet):
    """Filter for ProductionNode

    Extends filterset to include start and end filters.
    """

    start = django_filters.DateTimeFilter(method="start_filter")
    start__gte = django_filters.DateTimeFilter(method="start_filter")
    start__lte = django_filters.DateTimeFilter(method="start_filter")

    end = django_filters.DateTimeFilter(method="end_filter")
    end__gte = django_filters.DateTimeFilter(method="end_filter")
    end__lte = django_filters.DateTimeFilter(method="end_filter")

    def start_filter(self, query_set, value, date=None):
        return query_set.annotate_start().filter(**{value: date})

    def end_filter(self, query_set, value, date=None):
        return query_set.annotate_end().filter(**{value: date})

    class Meta:
        model = Production
        exclude = ("poster_image", "featured_image", "cover_image")

    @property
    def qs(self):
        return super().qs.user_can_see(self.request.user)

    order_by = ProductionByMethodOrderingFilter()


class SalesBreakdown(graphene.ObjectType):
    total_payments_value = graphene.Int(required=True)
    total_misc_costs_value = graphene.Int(required=True)
    total_society_income_value = graphene.Int(required=True)


class ProductionNode(PermissionsMixin, GrapheneEnumMixin, DjangoObjectType):
    warnings = DjangoListField(WarningNode)
    crew = DjangoListField(CrewMemberNode)
    cast = DjangoListField(CastMemberNode)
    production_team = DjangoListField(ProductionTeamMemberNode)

    start = graphene.DateTime()
    end = graphene.DateTime()

    is_bookable = graphene.Boolean(required=True)
    min_seat_price = graphene.Int()

    sales_breakdown = graphene.Field(SalesBreakdown)

    def resolve_start(self, info):
        return self.start_date()

    def resolve_end(self, info):
        return self.end_date()

    def resolve_is_bookable(self, info):
        return self.is_bookable()

    def resolve_min_seat_price(self, info):
        return self.min_seat_price()

    def resolve_sales_breakdown(self, info):
        if not info.context.user.has_perm(
            "productions.sales", self  # TOD!O: Use real permission here
        ):
            return None

        sales_breakdown = self.sales_breakdown

        return SalesBreakdown(
            total_payments_value=sales_breakdown["payments_total"],
            total_misc_costs_value=sales_breakdown["misc_costs_total"],
            total_society_income_value=sales_breakdown["society_income_total"],
        )

    class Meta:
        model = Production
        filterset_class = ProductionFilter
        interfaces = (relay.Node,)


class ConcessionTypeBookingType(graphene.ObjectType):
    """Node for ConcessionType which can be Booked.

    This object gives the information about a ConcessionType for a given
    production. It includes the concession type and its pricing.
    """

    concession_type = graphene.Field(ConcessionTypeNode)
    price = graphene.Int()
    price_pounds = graphene.String()

    def resolve_price_pounds(self, info):
        return "%.2f" % (self.price / 100)


class PerformanceSeatGroupNode(DjangoObjectType):
    capacity_remaining = graphene.Int()
    concession_types = graphene.List(ConcessionTypeBookingType)

    def resolve_concession_types(self, info):
        return [
            ConcessionTypeBookingType(
                concession_type=concession,
                price=self.performance.price_with_concession(concession, self),
            )
            for concession in self.performance.concessions()
        ]

    def resolve_capacity_remaining(self, info):
        return self.performance.capacity_remaining(self.seat_group)

    class Meta:
        model = PerformanceSeatGroup
        fields = (
            "capacity",
            "capacity_remaining",
            "concession_types",
            "seat_group",
        )
        filter_fields = {}  # type: ignore
        interfaces = (relay.Node,)


class PerformanceFilter(FilterSet):
    """Filter for PerformanceNode.

    Extends filterset to include orderby start.
    """

    has_boxoffice_permissions = django_filters.BooleanFilter(
        method="has_boxoffice_perm_filter"
    )
    run_on = django_filters.DateFilter(method="run_on_filter")

    class Meta:
        model = Performance
        exclude = ("performance_seat_groups", "bookings")

    order_by = django_filters.OrderingFilter(fields=(("start"),))

    def has_boxoffice_perm_filter(self, query_set, _, has_permission=None):
        return query_set.has_boxoffice_permission(
            self.request.user, has_permission=has_permission
        )

    def run_on_filter(self, query_set, _, date=None):
        return query_set.running_on(date)


class PerformanceTicketsBreakdown(graphene.ObjectType):
    total_capacity = graphene.Int(required=True)
    total_tickets_sold = graphene.Int(required=True)
    total_tickets_checked_in = graphene.Int(required=True)
    total_tickets_to_check_in = graphene.Int(required=True)
    total_tickets_available = graphene.Int(required=True)


class PerformanceNode(DjangoObjectType):
    capacity_remaining = graphene.Int()
    ticket_options = graphene.List(PerformanceSeatGroupNode)
    min_seat_price = graphene.Int()
    duration_mins = graphene.Int()
    is_inperson = graphene.Boolean(required=True)
    is_online = graphene.Boolean(required=True)
    sold_out = graphene.Boolean(required=True)
    discounts = DjangoListField(DiscountNode)
    tickets_breakdown = graphene.Field(PerformanceTicketsBreakdown, required=True)
    sales_breakdown = graphene.Field(SalesBreakdown)

    def resolve_ticket_options(self, info):
        return self.performance_seat_groups.all()

    def resolve_capacity_remaining(self, info):
        return self.capacity_remaining()

    def resolve_min_seat_price(self, info):
        return self.min_seat_price()

    def resolve_is_inperson(self, info):
        return True

    def resolve_is_online(self, info):
        return False

    def resolve_duration_mins(self, info):
        return self.duration().seconds // 60

    def resolve_sold_out(self, info):
        return self.is_sold_out()

    def resolve_tickets_breakdown(self, info):
        return PerformanceTicketsBreakdown(
            self.total_capacity,
            self.total_tickets_sold(),
            self.total_tickets_checked_in,
            self.total_tickets_unchecked_in,
            self.capacity_remaining(),
        )

    def resolve_sales_breakdown(self, info):
        if not info.context.user.has_perm(
            "productions.sales", self.production  # TOD!O: Use real permission here
        ):
            return None

        sales_breakdown = self.sales_breakdown

        return SalesBreakdown(
            total_payments_value=sales_breakdown["payments_total"],
            total_misc_costs_value=sales_breakdown["misc_costs_total"],
            total_society_income_value=sales_breakdown["society_income_total"],
        )

    class Meta:
        model = Performance
        filterset_class = PerformanceFilter
        interfaces = (relay.Node,)
        exclude = ("performance_seat_groups",)


class Query(graphene.ObjectType):
    """Query for production module.

    These queries are appended to the main schema Query.
    """

    productions = DjangoFilterConnectionField(ProductionNode)
    performances = DjangoFilterConnectionField(PerformanceNode)

    production = graphene.Field(ProductionNode, slug=graphene.String(required=True))
    performance = relay.Node.Field(PerformanceNode)

    def resolve_production(self, _, slug):
        try:
            return Production.objects.get(slug=slug)
        except Production.DoesNotExist:
            return None
