"""SeatService idempotency payload normalization (legacy vs new shape)."""

from skyhigh.services.seat_service import SeatService


def test_normalize_hold_idem_legacy_status_key() -> None:
    inner = {"seat_id": 3, "held_until": "2020-01-01T00:00:00+00:00", "status": "HELD"}
    out = SeatService._normalize_hold_idem(inner)
    assert out["seat_status"] == "HELD"
    assert out["seat_id"] == 3


def test_normalize_hold_idem_new_shape() -> None:
    inner = {"seat_id": 2, "held_until": None, "seat_status": "HELD"}
    out = SeatService._normalize_hold_idem(inner)
    assert out == inner


def test_normalize_confirm_idem_legacy() -> None:
    inner = {"seat_id": 4, "status": "CONFIRMED"}
    out = SeatService._normalize_confirm_idem(inner)
    assert out["seat_status"] == "CONFIRMED"
    assert out["seat_id"] == 4
