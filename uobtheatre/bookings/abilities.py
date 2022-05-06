from uobtheatre.users.abilities import Ability


class ModifyBooking(Ability):
    name = "modify_booking"

    @classmethod
    def user_has_for(cls, user, obj) -> bool:
        return obj.user.id == user.id or user.has_perm(
            "productions.boxoffice", obj.performance.production
        )
