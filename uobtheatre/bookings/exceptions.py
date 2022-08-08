from uobtheatre.utils.exceptions import GQLException


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
