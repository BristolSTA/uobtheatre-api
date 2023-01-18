import django_filters
import graphene
from django.db.models.aggregates import Sum
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
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import (
    AuthRequiredMixin,
    ModelDeletionMutation,
    SafeFormMutation,
)


class ConcessionTypeNode(DjangoObjectType):
    class Meta:
        model = ConcessionType
        interfaces = (relay.Node,)
        fields = ("name", "description", "max_per_booking")


class DiscountRequirementNode(DjangoObjectType):
    class Meta:
        model = DiscountRequirement
        interfaces = (relay.Node,)


class DiscountFilter(FilterSet):
    """Custom filter for DiscountFilter."""

    group = django_filters.BooleanFilter(method="filter_group", label="Group")

    class Meta:
        model = Discount
        fields = ("group",)

    def filter_group(self, queryset, _, value):
        """
        Filter discounts by whether they are a group discount.
        A group discount is a discount that requires more than 1 tickt to meet
        the discount requirements.
        """
        queryset = queryset.annotate(
            number_of_tickets_required=Sum("requirements__number")
        )
        return (
            queryset.filter(number_of_tickets_required__gt=1)
            if value
            else queryset.filter(number_of_tickets_required=1)
        )


class DiscountNode(DjangoObjectType):
    requirements = DjangoListField(DiscountRequirementNode)

    class Meta:
        model = Discount
        interfaces = (relay.Node,)
        filterset_class = DiscountFilter


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

        # If we are editing an exisiting discount, add the performances currently associated with that discount
        if instance:
            performances += instance.performances.prefetch_related("production").all()

        # Authorize user on all of the performance's productions
        for performance in performances or []:
            if not EditProduction.user_has_for(
                info.context.user, performance.production
            ):
                raise AuthorizationException(
                    "You do not have the ability to edit one of the provided performances"
                )

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

        # Get all the performances that are related to the requirement's discounts
        all_performances = []
        if instance:
            all_performances.extend(
                instance.discount.performances.prefetch_related("production").all()
            )
        if new_discount:
            all_performances.extend(
                new_discount.performances.prefetch_related("production").all()
            )

        # Authorize user on all of the performance's productions
        for performance in all_performances:
            if not EditProduction.user_has_for(
                info.context.user, performance.production
            ):
                raise AuthorizationException(
                    "You do not have permission to edit one or more of the productions associated with this requirement"
                )

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
                raise AuthorizationException(
                    "You do not have the ability to edit one of the provided performances"
                )

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
