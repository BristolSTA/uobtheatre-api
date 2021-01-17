import graphene
from graphene_django_extras import DjangoFilterListField, DjangoObjectType

from uobtheatre.bookings.models import ConcessionType
from uobtheatre.productions.models import Performance, PerformanceSeatGroup, Production


class ConcessionTypeType(DjangoObjectType):
    class Meta:
        model = ConcessionType


class ConcessionTypeBookingType(graphene.ObjectType):
    concession = graphene.Field(ConcessionTypeType)
    price = graphene.Int()
    price_pounds = graphene.Int()

    def resolve_price_pounds(self, info):
        return "%.2f" % (self.price / 100)


class ProductionType(DjangoObjectType):
    class Meta:
        model = Production
        filter_fields = {
            "id": ("exact",),
            "slug": ("exact",),
        }


class PerformanceSeatGroupType(DjangoObjectType):
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


class PerformanceType(DjangoObjectType):
    capacity_remaining = graphene.Int()
    ticket_options = graphene.List(PerformanceSeatGroupType)

    def resolve_ticket_options(self, info, **kwargs):
        return self.performance_seat_groups.all()

    def resolve_capacity_remaining(self, info):
        return self.capacity_remaining()

    class Meta:
        model = Performance
        filter_fields = {
            "id": ("exact",),
        }


class Query(graphene.ObjectType):
    productions = DjangoFilterListField(ProductionType)
    performances = DjangoFilterListField(PerformanceType)

    def resolve_productions(self, info, **kwargs):
        return Production.objects.all()

    def resolve_performances(self, info, **kwargs):
        return Performance.objects.all()
