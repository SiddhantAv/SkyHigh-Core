"""Domain exception metadata for structured API errors."""

from skyhigh.exceptions import (
    CheckInSessionNotFoundError,
    IdempotencyKeyMismatchError,
    InvalidPaymentStateError,
    PassengerHoldRateLimitedError,
    SeatAlreadyConfirmedError,
    SeatAlreadyHeldError,
    SeatHoldExpiredError,
    SeatNotFoundError,
    SeatNotReadyForCheckInError,
    WeightServiceError,
)


def test_seat_not_found_code_and_details() -> None:
    exc = SeatNotFoundError(5)
    assert exc.code == "SeatNotFound"
    assert exc.seat_id == 5
    assert "seat" in exc.message.lower()


def test_seat_already_held_default_message() -> None:
    exc = SeatAlreadyHeldError()
    assert exc.code == "SeatAlreadyHeld"
    assert len(exc.message) > 10


def test_checkin_session_not_found() -> None:
    exc = CheckInSessionNotFoundError(9)
    assert exc.code == "CheckInSessionNotFound"
    assert exc.session_id == 9


def test_all_codes_unique_strings() -> None:
    codes = [
        SeatNotFoundError(1).code,
        SeatAlreadyHeldError().code,
        SeatAlreadyConfirmedError().code,
        SeatHoldExpiredError().code,
        SeatNotReadyForCheckInError().code,
        CheckInSessionNotFoundError(1).code,
        InvalidPaymentStateError().code,
        IdempotencyKeyMismatchError().code,
        PassengerHoldRateLimitedError().code,
        WeightServiceError().code,
    ]
    assert len(codes) == len(set(codes))
