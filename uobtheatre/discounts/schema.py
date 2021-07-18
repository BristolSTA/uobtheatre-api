from django.db.models import Count
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType

from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement


class ConcessionTypeNode(DjangoObjectType):
    class Meta:
        model = ConcessionType
        interfaces = (relay.Node,)
        exclude = ("discountrequirement_set",)


class DiscountRequirementNode(DjangoObjectType):
    class Meta:
        model = DiscountRequirement
        interfaces = (relay.Node,)


class DiscountNode(DjangoObjectType):
    requirements = DjangoListField(DiscountRequirementNode)

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.annotate(
            number_of_tickets_required=Count("requirements__number")
        ).filter(number_of_tickets_required__gt=1)

    class Meta:
        model = Discount
        interfaces = (relay.Node,)
