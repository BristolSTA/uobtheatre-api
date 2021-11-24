import graphene

from uobtheatre.productions.abilities import AddProduction, EditProductionObjects
from uobtheatre.productions.forms import (
    PerformanceForm,
    PerformanceSeatGroupForm,
    ProductionForm,
)
from uobtheatre.productions.models import Performance, PerformanceSeatGroup, Production
from uobtheatre.productions.schema import (
    PerformanceNode,
    PerformanceSeatGroupNode,
    ProductionNode,
)
from uobtheatre.users.schema import AuthMutation
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLExceptions,
    SafeMutation,
)
from uobtheatre.utils.schema import (
    AssignPermissionsMutation,
    AuthRequiredMixin,
    IdInputField,
    ModelDeletionMutation,
    SafeFormMutation,
)


class SetProductionStatus(AuthRequiredMixin, SafeMutation):
    class Arguments:
        production_id = IdInputField(required=True)
        status = graphene.Argument(
            "uobtheatre.productions.schema.ProductionStatusSchema"
        )

    @classmethod
    def authorize_request(cls, _, info, production_id, status):
        update_status = status
        production = Production.objects.get(id=production_id)
        user = info.context.user

        # If they have permission to force change then they can change
        if user.has_perm("productions.force_change_production", production):
            return

        # If the user has permission to edit the production, they can:
        # - Submit a draft
        # - Publish and approved production
        if EditProductionObjects.user_has(user, production):
            # If the production has been approved they can publish it
            if (
                update_status == Production.Status.PUBLISHED
                and production.status == Production.Status.APPROVED
            ):
                return

            # If the production is a draft they can submit it for approval
            if (
                update_status == Production.Status.PENDING
                and production.status == Production.Status.DRAFT
            ):
                return

        # If they have permission to approve and they are tyring to approve a
        # pending.
        if (
            update_status == Production.Status.APPROVED
            and production.status == Production.Status.PENDING
            and user.has_perm("productions.approve_production", production)
        ):
            return

        # If they can do finance stuff then they can complete a production if it
        # has been closed.
        if (
            update_status == Production.Status.COMPLETE
            and production.status == Production.Status.CLOSED
            and user.has_perm("reports.finance_reports")
        ):
            return

        # In any other case they are unathorized
        raise AuthorizationException()

    @classmethod
    def resolve_mutation(cls, _, info, production_id: int, status: Production.Status):
        production = Production.objects.get(id=production_id)

        # If we are setting this production to anything other than draft it must
        # be valid.
        if status != Production.Status.DRAFT and (
            errors := production.validate_draft()
        ):
            raise GQLExceptions(errors)

        production.status = status
        production.save()

        return cls(success=True)


class ProductionMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a production"""

    production = graphene.Field(ProductionNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        return super().authorize_request(
            root, info, **inputs
        ) and cls.authorize_society_part(root, info, **inputs)

    @classmethod
    def authorize_society_part(cls, root, info, **inputs):
        """Authorise the society parameter if passed"""
        new_society = cls.get_python_value(root, info, "society", **inputs)
        has_perm_new_society = (
            info.context.user.has_perm("add_production", new_society)
            if new_society
            else True
        )
        return has_perm_new_society

    @classmethod
    def on_creation(cls, info, response):
        info.context.user.assign_perm("view_production", response.production)
        info.context.user.assign_perm("change_production", response.production)
        info.context.user.assign_perm("sales", response.production)
        info.context.user.assign_perm("boxoffice", response.production)

    class Meta:
        form_class = ProductionForm
        create_ability = AddProduction
        update_ability = EditProductionObjects


class ProductionPermissionsMutation(AssignPermissionsMutation):
    class Meta:
        model = Production


class PerformanceMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a performance"""

    performance = graphene.Field(PerformanceNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        return cls.authorize_production_part(root, info, **inputs)

    @classmethod
    def authorize_production_part(cls, root, info, **inputs):
        """Authorised the production part (exisiting and prodivded input)"""
        new_production = cls.get_python_value(root, info, "production", **inputs)
        has_perm_new_production = (
            EditProductionObjects.user_has(info.context.user, new_production)
            if new_production
            else True
        )

        if cls.is_creation:
            # If this is a creation operation, we care that there is a new production specified via args, and that the user has edit ability on this production
            return has_perm_new_production and new_production

        # For update operations, we care that the user has permissions on both the currently assigned production, and the new production (if provided)
        current_production = cls.get_object_instance(root, info, **inputs).production
        has_perm_current_production = EditProductionObjects.user_has(
            info.context.user, current_production
        )
        return has_perm_new_production and has_perm_current_production

    class Meta:
        form_class = PerformanceForm


class DeletePerformanceMutation(ModelDeletionMutation):
    """Mutation to delete a performance"""

    @classmethod
    def authorize_request(cls, _, info, **inputs):
        instance = cls.get_instance(inputs["id"])
        if not EditProductionObjects.user_has(info.context.user, instance.production):
            raise AuthorizationException

    class Meta:
        model = Performance


class PerformanceSeatGroupMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a performance seat group"""

    performanceSeatGroup = graphene.Field(PerformanceSeatGroupNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        new_performance = cls.get_python_value(root, info, "performance", **inputs)
        has_perm_new_performance = (
            EditProductionObjects.user_has(
                info.context.user, new_performance.production
            )
            if new_performance
            else True
        )

        if cls.is_creation:
            # If this is a creation operation, we care that there is a new performance specified via args, and that the user has edit ability on this production
            return has_perm_new_performance and new_performance

        # For update operations, we care that the user has permissions on both the currently assigned performance, and the new performance (if provided)
        current_performance = cls.get_object_instance(
            root, info, **inputs
        ).performance.production
        has_perm_current_performance = EditProductionObjects.user_has(
            info.context.user, current_performance
        )
        return has_perm_new_performance and has_perm_current_performance

    class Meta:
        form_class = PerformanceSeatGroupForm


class DeletePerformanceSeatGroupMutation(ModelDeletionMutation):
    """Mutation to delete a performance seat group"""

    @classmethod
    def authorize_request(cls, _, info, **inputs):
        instance = cls.get_instance(inputs["id"])
        return EditProductionObjects.user_has(
            info.context.user,
            instance.performance.production,
        )

    class Meta:
        model = PerformanceSeatGroup


class Mutation(AuthMutation, graphene.ObjectType):
    """Mutations for the productions module"""

    production = ProductionMutation.Field()
    production_permissions = ProductionPermissionsMutation.Field()

    performance = PerformanceMutation.Field()
    delete_performance = DeletePerformanceMutation.Field()

    performance_seat_group = PerformanceSeatGroupMutation.Field()
    delete_performance_seat_group = DeletePerformanceSeatGroupMutation.Field()

    set_production_status = SetProductionStatus.Field()
