from typing import Tuple
from uobtheatre.payments.payables import Payable
from uobtheatre.bookings.models import Booking 
from uobtheatre.users.abilities import Ability
from uobtheatre.productions.models import Performance 


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

class TransferBooking(Ability):

    name = "transfer_booking"
    
    @classmethod
    def user_has_for(cls, user, booking: Booking, performance: Performance) -> bool:
        # If the booking being transfered has any checked in tickets, it cannot
        # be transfered.
        if booking.tickets.filter(checked_in=True).exists():
            return False

        # Cannot transfer to the same performance
        if booking.performance == performance:
            raise BookingTransferPerformanceUnchangedException
        
        # Cannot transfer to a differnet production 
        if self.performance.production != performance.production:
            raise BookingTransferToDifferentProductionException

        return booking.status == Payable.Status.PAID and (
            booking.user.id == user.id
        )
