from uobtheatre.utils.exceptions import GQLException


class CantBeRefundedException(GQLException):
    def __init__(self, message="This object cannot be refunded") -> None:
        super().__init__(message=message)


class CantBeCanceledException(GQLException):
    def __init__(self, message="This transaction cannot be cancelled") -> None:
        super().__init__(message=message)
