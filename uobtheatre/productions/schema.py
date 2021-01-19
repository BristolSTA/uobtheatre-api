import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.bookings.schema import ConcessionTypeNode
from uobtheatre.productions.models import Performance, PerformanceSeatGroup, Production
from uobtheatre.utils.schema import (
    GrapheneImageField,
    GrapheneImageFieldNode,
    GrapheneImageMixin,
)


class ProductionNode(GrapheneImageMixin, DjangoObjectType):
    cover_image = GrapheneImageField(GrapheneImageFieldNode)
    featured_image = GrapheneImageField(GrapheneImageFieldNode)
    poster_image = GrapheneImageField(GrapheneImageFieldNode)

    class Meta:
        model = Production
        filter_fields = {
            "id": ("exact",),
            "slug": ("exact",),
        }
        fields = "__all__"
        interfaces = (relay.Node,)


class ConcessionTypeBookingType(graphene.ObjectType):
    concession = graphene.Field(ConcessionTypeNode)
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
                concession=concession,
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
        filter_fields = {}
        interfaces = (relay.Node,)


class PerformanceNode(DjangoObjectType):
    capacity_remaining = graphene.Int()
    ticket_options = graphene.List(PerformanceSeatGroupNode)

    def resolve_ticket_options(self, info, **kwargs):
        return self.performance_seat_groups.all()

    def resolve_capacity_remaining(self, info):
        return self.capacity_remaining()

    class Meta:
        model = Performance
        filter_fields = {
            "id": ("exact",),
        }
        fields = (
            "id",
            "capacity",
            "doors_open",
            "end",
            "extra_information",
            "production",
            "start",
            "capacity_remaining",
            "ticket_options",
        )
        interfaces = (relay.Node,)


class Query(graphene.ObjectType):
    production = relay.Node.Field(ProductionNode)
    productions = DjangoFilterConnectionField(ProductionNode)

    performance = relay.Node.Field(PerformanceNode)
    performances = DjangoFilterConnectionField(PerformanceNode)
