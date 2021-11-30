from uobtheatre.users.abilities import Ability


class AddProduction(Ability):
    """Whether the user is able to change a production's details and sub-objects"""

    name = "add_production"

    @staticmethod
    def user_has(user, _) -> bool:
        return user.has_any_objects_with_perms(
            ["societies.add_production"]
        ) or user.has_perm("productions.add_production")


class EditProductionObjects(Ability):
    """Whether the user is able to change a production's details and sub-objects, based on the current status"""

    name = "edit_production_objects"

    @staticmethod
    def user_has(user, obj) -> bool:
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
