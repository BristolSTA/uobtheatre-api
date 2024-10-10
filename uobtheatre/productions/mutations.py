from typing import Optional

import graphene
from guardian.shortcuts import get_users_with_perms

from uobtheatre.productions.abilities import AddProduction, EditProduction
from uobtheatre.productions.emails import (
    send_production_approved_email,
    send_production_needs_changes_email,
    send_production_ready_for_review_email,
)
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
from uobtheatre.users.models import User
from uobtheatre.users.schema import AuthMutation
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLExceptions,
    SafeMutation,
)
from uobtheatre.utils.permissions import get_users_with_perm
from uobtheatre.utils.schema import (
    AssignPermissionsMutation,
    AuthRequiredMixin,
    IdInputField,
    ModelDeletionMutation,
    SafeFormMutation,
)


class SetProductionStatus(AuthRequiredMixin, SafeMutation):
    """
    Mutation to set the status of a production.
    """

    class Arguments:
        production_id = IdInputField(required=True)
        status = graphene.Argument(
            "uobtheatre.productions.schema.ProductionStatusSchema"
        )
        message = graphene.String()

    @classmethod
    # pylint: disable=arguments-differ
    def authorize_request(cls, _, info, production_id, status, **__):
        update_status = status
        production = Production.objects.get(id=production_id)
        user = info.context.user

        # If they have permission to force change then they can change
        if user.has_perm("productions.force_change_production", production):
            return

        # If the user has permission to edit the production, they can:
        # - Submit a draft to pending
        # - Publish an approved production
        if user.has_perm("productions.change_production", production):
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

        # If they have permission to approve they can either approve or reject a pending production
        if (
            update_status in [Production.Status.APPROVED, Production.Status.DRAFT]
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
    def resolve_mutation(
        cls,
        _,
        info,
        production_id: int,
        status: Production.Status,
        message: Optional[str] = None,
    ):
        production = Production.objects.get(id=production_id)
        previous_status = production.status

        # If we are setting this production to anything other than draft it must
        # be valid.
        if status != Production.Status.DRAFT and (error := production.validate()):
            raise error

        production.status = status
        production.save()

        # Notify if applicable
        involved_users = get_users_with_perms(
            production, only_with_perms_in=["change_production"]
        )

        if status == Production.Status.PENDING:
            approving_users = get_users_with_perm(
                "productions.approve_production", production
            ).all()
            for user in approving_users:
                send_production_ready_for_review_email(user, production)

        elif (
            status == Production.Status.APPROVED
            and previous_status == Production.Status.PENDING
        ):
            for user in involved_users:
                send_production_approved_email(user, production)

        elif (
            status == Production.Status.DRAFT
            and previous_status == Production.Status.PENDING
        ):
            for user in involved_users:
                send_production_needs_changes_email(user, production, message)

        return cls(success=True)


class ProductionMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a production"""

    production = graphene.Field(ProductionNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        super().authorize_request(root, info, **inputs)

        cls.authorize_society_part(root, info, **inputs)

    @classmethod
    def authorize_society_part(cls, root, info, **inputs):
        """Authorise the society parameter if passed"""
        new_society = cls.get_python_value(root, info, inputs, "society")
        current_production = cls.get_object_instance(root, info, **inputs)
        current_society = current_production.society if current_production else None

        has_perm_new_society = (
            info.context.user.has_perm("add_production", new_society)
            if new_society and not new_society == current_society
            else True
        )
        if not has_perm_new_society:
            raise AuthorizationException(
                "You do not have permission to add a production for this society",
                field="society",
            )

    @classmethod
    def on_creation(cls, info, response):
        info.context.user.assign_perm("view_production", response.production)
        info.context.user.assign_perm("view_bookings", response.production)
        info.context.user.assign_perm("change_production", response.production)
        info.context.user.assign_perm("sales", response.production)
        info.context.user.assign_perm("boxoffice", response.production)

    class Meta:
        form_class = ProductionForm
        create_ability = AddProduction
        update_ability = EditProduction


class ProductionPermissionsMutation(AssignPermissionsMutation):
    class Meta:
        model = Production


def authorize_productions(
    old_production: Optional[Production],
    new_production: Optional[Production],
    user: User,
    object_name: str,
    field: str,
):
    """Authorize the user on both the old and new production"""

    # If the performance is current assinged to a production and being move
    # to a different production then we must check the user has permission
    # to edit the performances curent production.
    if old_production and not EditProduction.user_has_for(user, old_production):
        raise AuthorizationException(
            f"You do not have permission to move the {object_name} from the current {field}",
            field=field,
        )

    # If the performance is being assigned to a production then we must
    # check the user has permission to edit this new production.
    if new_production and not EditProduction.user_has_for(user, new_production):
        raise AuthorizationException(
            f"You do not have permission to add the {object_name} to this {field}",
            field=field,
        )


class PerformanceMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a performance"""

    performance = graphene.Field(PerformanceNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        current_instance = cls.get_object_instance(root, info, **inputs)
        authorize_productions(
            current_instance.production if current_instance else None,
            cls.get_python_value(root, info, inputs, "production"),
            info.context.user,
            "performance",
            "production",
        )

    class Meta:
        form_class = PerformanceForm


class DeletePerformanceMutation(ModelDeletionMutation):
    """Mutation to delete a performance"""

    @classmethod
    def authorize_request(cls, _, info, **inputs):
        instance = cls.get_instance(inputs["id"])
        if not EditProduction.user_has_for(info.context.user, instance.production):
            raise AuthorizationException

    class Meta:
        model = Performance


class PerformanceSeatGroupMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a performance seat group"""

    performanceSeatGroup = graphene.Field(PerformanceSeatGroupNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        new_performance = cls.get_python_value(root, info, inputs, "performance")
        current_instance = cls.get_object_instance(root, info, **inputs)

        authorize_productions(
            current_instance.performance.production if current_instance else None,
            new_performance.production if new_performance else None,
            info.context.user,
            "seat group",
            "performance",
        )

    class Meta:
        form_class = PerformanceSeatGroupForm


class DeletePerformanceSeatGroupMutation(ModelDeletionMutation):
    """Mutation to delete a performance seat group"""

    @classmethod
    def authorize_request(cls, _, info, **inputs):
        instance = cls.get_instance(inputs["id"])
        return EditProduction.user_has_for(
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
