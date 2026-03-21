"""Domain errors — structured `error` + `message` in API handlers."""


class SeatNotFoundError(Exception):
    code = "SeatNotFound"

    def __init__(self, seat_id: int, message: str | None = None) -> None:
        self.seat_id = seat_id
        self.message = message or "No seat was found for this identifier."
        super().__init__(self.message)


class SeatAlreadyHeldError(Exception):
    code = "SeatAlreadyHeld"

    def __init__(self, message: str | None = None) -> None:
        self.message = (
            message
            or "This seat is already reserved by another passenger or is not available to select."
        )
        super().__init__(self.message)


class SeatAlreadyConfirmedError(Exception):
    code = "SeatAlreadyConfirmed"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or "This seat is already confirmed and cannot be held or changed."
        super().__init__(self.message)


class SeatHoldExpiredError(Exception):
    code = "SeatHoldExpired"

    def __init__(self, message: str | None = None) -> None:
        self.message = (
            message
            or "Your seat hold has expired. Please select the seat again within the time limit."
        )
        super().__init__(self.message)


class CheckInSessionNotFoundError(Exception):
    code = "CheckInSessionNotFound"

    def __init__(self, session_id: int, message: str | None = None) -> None:
        self.session_id = session_id
        self.message = message or "No check-in session was found for this identifier."
        super().__init__(self.message)


class SeatNotReadyForCheckInError(Exception):
    code = "SeatNotReadyForCheckIn"

    def __init__(self, message: str | None = None) -> None:
        self.message = (
            message
            or "This seat is not confirmed for you yet. Confirm your seat before starting check-in."
        )
        super().__init__(self.message)


class InvalidPaymentStateError(Exception):
    code = "InvalidPaymentState"

    def __init__(self, message: str | None = None) -> None:
        self.message = (
            message
            or "Payment cannot be completed for this check-in in its current state."
        )
        super().__init__(self.message)


class IdempotencyKeyMismatchError(Exception):
    code = "IdempotencyKeyMismatch"

    def __init__(self, message: str | None = None) -> None:
        self.message = (
            message
            or "This idempotency key was already used for a different seat. Use a new key for this request."
        )
        super().__init__(self.message)


class PassengerHoldRateLimitedError(Exception):
    code = "PassengerHoldRateLimited"

    def __init__(self, message: str | None = None) -> None:
        self.message = (
            message
            or "Too many seat-hold attempts for this passenger. Please wait a minute and try again."
        )
        super().__init__(self.message)


class WeightServiceError(Exception):
    code = "WeightServiceUnavailable"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or "The weight verification service could not be reached or returned an error."
        super().__init__(self.message)
