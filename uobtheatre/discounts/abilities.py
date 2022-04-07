from uobtheatre.discounts.models import ConcessionType, Discount
from uobtheatre.productions.abilities import EditProduction
from uobtheatre.productions.models import Performance, Production
from uobtheatre.users.abilities import Ability
from uobtheatre.users.models import User


class CreateConcessionType(Ability):
    """Whether the user can create a new concession type"""

    name = "create_concession_type"

    @staticmethod
    def user_has(user: User) -> bool:
        return EditProduction.user_has(user)


class ModifyConcessionType(Ability):
    """Whether the user can modify or delete and exisiting concession type"""

    name = "modify_concession_type"

    @staticmethod
    def user_has_for(user: User, obj: ConcessionType) -> bool:
        discounts = Discount.objects.filter(
            requirements__in=obj.discount_requirements.prefetch_related(  # type: ignore
                "discount__performances__production"
            ).all()
        )
        performances = Performance.objects.filter(discounts__in=discounts)
        unique_productions_using_it = Production.objects.filter(
            performances__in=performances
        ).distinct()

        if not unique_productions_using_it.count() == 1:
            return False

        return EditProduction.user_has_for(user, unique_productions_using_it.first())
