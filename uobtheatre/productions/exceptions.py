from uobtheatre.utils.exceptions import GQLException


class UnassignedSeatGroupException(GQLException):
    """Raised when an unassigned seat group is encountered"""


class UnassignedConcessionTypeException(GQLException):
    """Raised when an unassigned seat group is encountered"""


class CapacityException(GQLException):
    """Raised when a request would cause a performance/seat gorup to go over capacity"""


class NotBookableException(GQLException):
    """Raised when a booking for a performance that is not bookable is requested"""

    def __init__(self, message="Performance not bookable") -> None:
        super().__init__(message)


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
