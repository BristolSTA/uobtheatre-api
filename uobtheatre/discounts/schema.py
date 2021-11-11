import graphene
from django.db.models import Count
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType

from uobtheatre.discounts.abilities import CreateConcessionType, ModifyConcessionType
from uobtheatre.discounts.forms import ConcessionTypeForm
from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement
from uobtheatre.users.schema import AuthMutation
from uobtheatre.utils.schema import (
    AuthRequiredMixin,
    ModelDeletionMutation,
    SafeFormMutation,
)


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


class ConcessionTypeMutation(SafeFormMutation, AuthRequiredMixin):
    class Meta:
        form_class = ConcessionTypeForm
        create_ability = CreateConcessionType
        update_ability = ModifyConcessionType


class DeleteConcessionTypeMutation(ModelDeletionMutation):
    class Meta:
        model = ConcessionType
        ability = ModifyConcessionType


class Mutation(AuthMutation, graphene.ObjectType):
    concession_type = ConcessionTypeMutation.Field()
    delete_concession_type = DeleteConcessionTypeMutation.Field()
