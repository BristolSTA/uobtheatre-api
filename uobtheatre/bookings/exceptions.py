from typing import TYPE_CHECKING
from uobtheatre.utils.exceptions import GQLException

if TYPE_CHECKING:
    from uobtheatre.payments.payables import Payable


class BookingTransferPerformanceUnchangedException(GQLException):
    """Raised when a booking for a performance that is not bookable is requested"""

    def __init__(self) -> None:
        super().__init__("You cannot transfer a booking to the same performance")


class BookingTransferToDifferentProductionException(GQLException):
    """Raised when a booking for a performance that is not bookable is requested"""

    def __init__(self) -> None:
        super().__init__(
            "A booking can only be transfered to a performance of the same production"
        )


class BookingTransferBookingNotPaidException(GQLException):
    def __init__(self, status_display: str) -> None:
        super().__init__(f"A booking which is {status_display} cannot be transfered")
