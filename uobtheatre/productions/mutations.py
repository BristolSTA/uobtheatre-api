import graphene

from uobtheatre.utils.exceptions import (
    AuthorizationException,
    SafeMutation,
    GQLExceptions,
)
from uobtheatre.utils.schema import AuthRequiredMixin, IdInputField
from uobtheatre.productions.abilities import EditProductionObjects
from uobtheatre.productions.models import Production


class SetProductionStatus(AuthRequiredMixin, SafeMutation):
    class Arguments:
        production_id = IdInputField(required=True)
        status = graphene.Argument(
            "uobtheatre.productions.schema.ProductionStatusSchema"
        )

    @classmethod
    def authorize_request(cls, _, info, production_id, status):
        production = Production.objects.get(id=production_id)
        user = info.context.user

        # If they have permission to force change then they can change
        if user.has_perm("force_change_production", production):
            return

        # If the user has permission to edit the production, they can:
        # - Submit a draft
        # - Publish and approved production
        if EditProductionObjects.user_has(user, production):
            # If the production has been approved they can publish it
            if (
                status == Production.Status.PUBLISHED
                and production.status == Production.Status.APPROVED
            ):
                return

            # If the production is a draft they can submit it for approval
            if (
                status == Production.Status.PENDING
                and production.status == Production.Status.DRAFT
            ):
                return

        # If they have permission to approve and they are tyring to approve a
        # pending.
        if (
            status == Production.Status.APPROVED
            and production.status == Production.Status.PENDING
            and user.has_perm("productions.approve_production", production)
        ):
            return

        # If they can do finance stuff then they can complete a production if it
        # has been closed.
        if (
            status == Production.Status.COMPLETE
            and production.status == Production.Status.CLOSED
            and user.has_perm("reports.finance_reports", production)
        ):
            return

        # In any other case they are unathorized
        raise AuthorizationException()

    @classmethod
    def resolve_mutation(cls, _, info, production_id: int, status: Production.Status):
        production = Production.objects.get(id=production_id)

        # If we are setting this production to anything other than draft it must
        # be valid.
        if status != Production.Status.DRAFT:
            errors = production.validate_draft()
            if errors:
                raise GQLExceptions(errors)

        production.status = status
        production.save()
