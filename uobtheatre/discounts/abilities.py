from uobtheatre.discounts.models import ConcessionType
from uobtheatre.productions.abilities import EditProductionObjects
from uobtheatre.users.abilities import Ability
from uobtheatre.users.models import User


class CreateConcessionType(Ability):
    """Whether the user can create a new concession type"""

    name = "create_concession_type"

    @staticmethod
    def user_has(user: User, _) -> bool:
        return user.has_any_objects_with_perms("productions.change_production")


class ModifyConcessionType(Ability):
    """Whether the user can modify or delete and exisiting concession type"""

    name = "modify_concession_type"

    @staticmethod
    def user_has(user: User, obj: ConcessionType) -> bool:
        unique_productions_using_it = list(
            set(  # pylint: disable=R1718
                [
                    performance.production
                    for requirement in obj.discount_requirements.prefetch_related(
                        "discount__performances__production"
                    ).all()
                    for performance in requirement.discount.performances.all()
                ]
            )
        )

        if not len(unique_productions_using_it) == 1:
            return False

        return EditProductionObjects.user_has(user, unique_productions_using_it[0])
