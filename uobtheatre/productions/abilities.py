from uobtheatre.productions.models import Performance
from uobtheatre.users.abilities import Ability


class AddProduction(Ability):
    """Whether the user is able to add a production"""

    name = "add_production"

    @staticmethod
    def user_has(user) -> bool:
        return user.has_perm(
            "productions.add_production"
        ) or user.has_any_objects_with_perms(["societies.add_production"])


class EditProduction(Ability):
    """
    Whether the user is able to change a production's details and
    sub-objects, based on the current status
    """

    name = "edit_production"

    @staticmethod
    def user_has(user):
        return user.has_any_objects_with_perms(
            [
                "productions.change_production",
                "productions.force_change_production",
                "productions.approve_production",
            ]
        )

    @staticmethod
    def user_has_for(user, obj) -> bool:
        from uobtheatre.productions.models import Production

        return (
            user.has_perm("productions.force_change_production", obj)
            or (
                user.has_perm("productions.change_production", obj)
                and obj.status == Production.Status.DRAFT
            )
            or (
                user.has_perm("productions.approve_production", obj)
                and obj.status == Production.Status.PENDING
            )
        )


class BookForPerformance(Ability):
    """Determine if the user can book for performances"""

    name = "book"

    @staticmethod
    def user_has(_):
        return True

    @staticmethod
    def user_has_for(user, obj: Performance) -> bool:
        from uobtheatre.productions.models import Production

        return obj.is_bookable and (
            obj.production.status
            == Production.Status.PUBLISHED  # Must be bookable and published
            or (
                EditProduction.user_has_for(
                    user, obj
                )  # If the user can edit the production
                and obj.production.status
                in [
                    Production.Status.APPROVED,
                    Production.Status.PUBLISHED,
                ]  # and the status is approved or published (e.g. creating comps)
            )
        )
