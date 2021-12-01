from uobtheatre.users.abilities import Ability
from uobtheatre.users.models import User
from uobtheatre.productions.abilities import EditProduction


class UplaodImage(Ability):
    """Whether the user has permission to open the boxoffice."""

    name = "upload_image"

    @staticmethod
    def user_has(user: User) -> bool:
        return EditProduction.user_has(user)
