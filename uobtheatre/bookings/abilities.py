from uobtheatre.payments.payables import Payable
from uobtheatre.users.abilities import Ability


class ModifyBooking(Ability):
    """Checks if the user has the ability to edit a booking (i.e. it's tickets or performance)"""

    name = "modify_booking"

    @classmethod
    def user_has_for(cls, user, obj) -> bool:
        # Must be in progress, and the user must own the booking or be able to box office for the performance of the booking
        return obj.status == Payable.Status.IN_PROGRESS and (
            obj.user.id == user.id
            or user.has_perm("productions.boxoffice", obj.performance.production)
        )


class ModifyAccessibility(Ability):
    """Checks if the user has the ability to edit the accessibility information of a booking"""

    name = "modify_accessibility"

    @classmethod
    def user_has_for(cls, user, obj) -> bool:
        # Must be paid, and the user must own the booking or be able to box office for the performance of the booking
        return obj.status == Payable.Status.PAID and (
            obj.user.id == user.id
            or user.has_perm("productions.boxoffice", obj.performance.production)
        )
