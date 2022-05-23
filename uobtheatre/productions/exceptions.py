from uobtheatre.utils.exceptions import GQLException


class InvalidSeatGroupException(GQLException):
    """Raised when a seat group is supplied that is invalid for a given performance"""

    def __init__(
        self,
        message="The supplied seat group is not valid for the given performance",
        **kwargs
    ) -> None:
        super().__init__(message=message, **kwargs)


class NotEnoughCapacityException(GQLException):
    """Raised when there is not enough capacity in a given object (performance, seat group, etc.)"""

    def __init__(
        self, message="There is not enough capacity available", **kwargs
    ) -> None:
        super().__init__(message=message, **kwargs)
