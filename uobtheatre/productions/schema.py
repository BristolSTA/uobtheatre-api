import django_filters
import graphene
from graphene import relay
from graphene_django import DjangoListField
from graphene_django.filter import (
    DjangoFilterConnectionField,
    GlobalIDFilter,
    GlobalIDMultipleChoiceFilter,
)

from uobtheatre.bookings.schema import ConcessionTypeNode, DiscountNode
from uobtheatre.productions.models import (
    AudienceWarning,
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionTeamMember,
    append_production_qs,
)
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

    def filter(self, query_set, value: str):  # pylint: disable=arguments-differ
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
            return append_production_qs(query_set, start=True).order_by("start")
        if value and "-start" in value:
            return append_production_qs(query_set, start=True).order_by("-start")

        if value and "end" in value:
            return append_production_qs(query_set, end=True).order_by("end")
        if value and "-end" in value:
            return append_production_qs(query_set, end=True).order_by("-end")

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
        return append_production_qs(query_set, start=True).filter(**{value: date})

    def end_filter(self, query_set, value, date=None):
        return append_production_qs(query_set, end=True).filter(**{value: date})

    class Meta:
        model = Production
        exclude = ("poster_image", "featured_image", "cover_image")

    order_by = ProductionByMethodOrderingFilter()


class ProductionNode(DjangoObjectType):
    warnings = DjangoListField(WarningNode)
    crew = DjangoListField(CrewMemberNode)
    cast = DjangoListField(CastMemberNode)
    production_team = DjangoListField(ProductionTeamMemberNode)

    start = graphene.DateTime()
    end = graphene.DateTime()

    is_bookable = graphene.Boolean(required=True)
    min_seat_price = graphene.Int()

    def resolve_start(self, info):
        return self.start_date()

    def resolve_end(self, info):
        return self.end_date()

    def resolve_is_bookable(self, info):
        return self.is_bookable()

    def resolve_min_seat_price(self, info):
        return self.min_seat_price()

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

    start = django_filters.DateTimeFilter(method="start_filter")

    class Meta:
        model = Performance
        exclude = ("performance_seat_groups", "bookings")

    order_by = django_filters.OrderingFilter(fields=(("start"),))


class PerformanceNode(DjangoObjectType):
    capacity_remaining = graphene.Int()
    ticket_options = graphene.List(PerformanceSeatGroupNode)
    min_seat_price = graphene.Int()
    duration_mins = graphene.Int()
    is_inperson = graphene.Boolean(required=True)
    is_online = graphene.Boolean(required=True)
    sold_out = graphene.Boolean(required=True)
    discounts = DjangoListField(DiscountNode)

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

    def resolve_production(self, info, slug):
        try:
            return Production.objects.get(slug=slug)
        except Production.DoesNotExist:
            return None
