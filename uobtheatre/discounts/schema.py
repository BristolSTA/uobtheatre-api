import graphene
from django.db.models import Count
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType

from uobtheatre.discounts.abilities import CreateConcessionType, ModifyConcessionType
from uobtheatre.discounts.forms import (
    ConcessionTypeForm,
    DiscountForm,
    DiscountRequirementForm,
)
from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement
from uobtheatre.productions.abilities import EditProduction
from uobtheatre.utils.exceptions import AuthorizationException
from uobtheatre.utils.schema import (
    AuthRequiredMixin,
    ModelDeletionMutation,
    SafeFormMutation,
)


class ConcessionTypeNode(DjangoObjectType):
    class Meta:
        model = ConcessionType
        interfaces = (relay.Node,)
        exclude = ("discount_requirements",)


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
        )

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


class DiscountMutation(SafeFormMutation, AuthRequiredMixin):
    """Create or update a discount"""

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        performances = cls.get_python_value(
            root, info, inputs, "performances", default=[]
        )
        instance = cls.get_object_instance(root, info, **inputs)

        if instance:
            performances += instance.performances.prefetch_related("production").all()

        if not performances:
            raise AuthorizationException

        # Authorize user on all of the performance's productions
        for performance in performances:
            if not EditProduction.user_has_for(
                info.context.user, performance.production
            ):
                raise AuthorizationException

    class Meta:
        form_class = DiscountForm


class DeleteDiscountMutation(ModelDeletionMutation):
    """Delete a discount"""

    @classmethod
    def authorize_request(cls, _, info, **inputs):
        discount = cls.get_instance(inputs["id"])
        for performance in discount.performances.prefetch_related("production").all():
            if not EditProduction.user_has_for(
                info.context.user, performance.production
            ):
                raise AuthorizationException

    class Meta:
        model = Discount


class DiscountRequirementMutation(SafeFormMutation, AuthRequiredMixin):
    """Create or update a discount"""

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        new_discount = cls.get_python_value(root, info, inputs, "discount") or None

        instance = cls.get_object_instance(root, info, **inputs)

        current_performances = (
            instance.discount.performances.prefetch_related("production").all()
            if instance
            else []
        )

        all_performances = []
        all_performances.extend(current_performances)
        if new_discount:
            all_performances.extend(new_discount.performances.all())

        if len(all_performances) == 0:
            raise AuthorizationException

        # Authorize user on all of the performance's productions
        for performance in all_performances:
            if not EditProduction.user_has_for(
                info.context.user, performance.production
            ):
                raise AuthorizationException

        return True

    class Meta:
        form_class = DiscountRequirementForm


class DeleteDiscountRequirementMutation(ModelDeletionMutation):
    """Delete a discount"""

    @classmethod
    def authorize_request(cls, _, info, **inputs):
        instance = cls.get_instance(inputs["id"])
        for performance in instance.discount.performances.prefetch_related(
            "production"
        ).all():
            if not EditProduction.user_has_for(
                info.context.user, performance.production
            ):
                raise AuthorizationException()

    class Meta:
        model = DiscountRequirement


class Mutation(graphene.ObjectType):
    """Discount mutations"""

    concession_type = ConcessionTypeMutation.Field()
    delete_concession_type = DeleteConcessionTypeMutation.Field()

    discount = DiscountMutation.Field()
    delete_discount = DeleteDiscountMutation.Field()

    discount_requirement = DiscountRequirementMutation.Field()
    delete_discount_requirement = DeleteDiscountRequirementMutation.Field()
