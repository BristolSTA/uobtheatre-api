import django_filters
import graphene
from django.db.models import Min, OuterRef, Subquery
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType
from graphene_django.filter import (
    DjangoFilterConnectionField,
    GlobalIDFilter,
    GlobalIDMultipleChoiceFilter,
)

from uobtheatre.bookings.schema import ConcessionTypeNode
from uobtheatre.productions.models import (
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionTeamMember,
    Warning,
)
from uobtheatre.utils.schema import (
    FilterSet,
    GrapheneImageField,
    GrapheneImageFieldNode,
    GrapheneImageMixin,
)


class CrewRoleNode(DjangoObjectType):
    class Meta:
        model = CrewRole
        interfaces = (relay.Node,)


class CastMemberNode(GrapheneImageMixin, DjangoObjectType):
    profile_picture = GrapheneImageField(GrapheneImageFieldNode)

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
        model = Warning
        interfaces = (relay.Node,)


class ProductionByMethodOrderingFilter(django_filters.OrderingFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra["choices"] += [
            ("start", "Start"),
            ("-start", "Start (descending)"),
        ]

    def filter(self, qs, value):
        if value and "start" in value:
            print("value is start")
            production_performances = Performance.objects.filter(
                production=OuterRef("pk"),
            ).values("start")

            qs.annotate(
                performances__start_date=Subquery(
                    production_performances.aggregate(min=Min("start")).values("min")
                )  # Annotate the proudction query with the start time
            ).order_by("performances__start_date")
            return qs.order_by("performances__start")
        # if value and "-start" in value:
        #     return qs.order_by("-performances__start")

        return super().filter(qs, value)


class ProductionFilter(FilterSet):
    class Meta:
        model = Production
        exclude = ("poster_image", "featured_image", "cover_image")

    order_by = ProductionByMethodOrderingFilter()


class ProductionNode(GrapheneImageMixin, DjangoObjectType):
    cover_image = GrapheneImageField(GrapheneImageFieldNode)
    featured_image = GrapheneImageField(GrapheneImageFieldNode)
    poster_image = GrapheneImageField(GrapheneImageFieldNode)

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
                price=self.performance.price_with_concession(concession, self.price),
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

    start = django_filters.DateTimeFilter(method="start_filter")

    class Meta:
        model = Performance
        exclude = ("performance_seat_groups", "bookings")

    order_by = django_filters.OrderingFilter(fields=(("start"),))


class PerformanceNode(DjangoObjectType):
    capacity_remaining = graphene.Int()
    ticket_options = graphene.List(PerformanceSeatGroupNode)
    min_seat_price = graphene.Int()

    def resolve_ticket_options(self, info, **kwargs):
        return self.performance_seat_groups.all()

    def resolve_capacity_remaining(self, info):
        return self.capacity_remaining()

    def resolve_min_seat_price(self, info):
        return self.min_seat_price()

    class Meta:
        model = Performance
        filterset_class = PerformanceFilter
        interfaces = (relay.Node,)
        exclude = ("performance_seat_groups", "bookings")


class Query(graphene.ObjectType):
    productions = DjangoFilterConnectionField(ProductionNode)
    performances = DjangoFilterConnectionField(PerformanceNode)

    production = graphene.Field(ProductionNode, slug=graphene.String(required=True))
    performance = relay.Node.Field(PerformanceNode)

    def resolve_production(self, info, slug):
        return Production.objects.get(slug=slug)
