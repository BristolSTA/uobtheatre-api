from uobtheatre.utils.exceptions import GQLException


class CantBeRefundedException(GQLException):
    def __init__(self, message="This object cannot be refunded") -> None:
        super().__init__(message)


class CantBeCanceledException(GQLException):
    def __init__(self, message="This transaction cannot be cancelled") -> None:
        super().__init__(message)


class CantBePaidForException(GQLException):
    def __init__(self, message="This payable cannot be paid for") -> None:
        super().__init__(message)


class TransferUnpaidPayableException(GQLException):
    def __init__(self, status_display: str) -> None:
        super().__init__(f"A payable which is {status_display} cannot be transfered")
