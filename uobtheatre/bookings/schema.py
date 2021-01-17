import graphene
from graphene_django import DjangoObjectType

from uobtheatre.productions.models import Performance, Production


class ProductionType(DjangoObjectType):
    class Meta:
        model = Production


class PerformanceType(DjangoObjectType):
    class Meta:
        model = Performance


class Query(graphene.ObjectType):
    productions = graphene.List(ProductionType)
    Performances = graphene.List(PerformanceType)

    def resolve_productions(self, info, **kwargs):
        return Production.objects.all()

    def resolve_performance(self, info, **kwargs):
        return Performance.objects.all()
