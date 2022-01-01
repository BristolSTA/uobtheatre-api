from uobtheatre.productions.abilities import EditProduction
from uobtheatre.users.abilities import Ability
from uobtheatre.users.models import User


class UploadImage(Ability):
    """Whether the user has permission to upload an image."""

    name = "upload_image"

    @staticmethod
    def user_has(user: User) -> bool:
        return EditProduction.user_has(user)
