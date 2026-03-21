from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HoldSeatRequest(BaseModel):
    passenger_id: int = Field(..., ge=1, examples=[1])
    idempotency_key: str = Field(..., min_length=1, max_length=512, examples=["hold-550e8400"])


class HoldSeatData(BaseModel):
    seat_id: int
    held_until: datetime | None = None


class HoldSeatApiResponse(BaseModel):
    """Standard success envelope for seat hold."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "HELD",
                    "message": "Seat successfully reserved for 2 minutes. Complete your booking before it expires.",
                    "data": {"seat_id": 12, "held_until": "2025-01-01T12:02:00+00:00"},
                }
            ]
        }
    )

    status: str = Field(..., description="Seat lifecycle status after the operation.")
    message: str = Field(..., description="Human-readable outcome for clients and support.")
    data: HoldSeatData


class ConfirmSeatRequest(BaseModel):
    passenger_id: int = Field(..., ge=1, examples=[1])
    idempotency_key: str = Field(..., min_length=1, max_length=512, examples=["confirm-550e8400"])


class ConfirmSeatData(BaseModel):
    seat_id: int


class ConfirmSeatApiResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "CONFIRMED",
                    "message": "Your seat is now confirmed. You can proceed to check-in.",
                    "data": {"seat_id": 12},
                }
            ]
        }
    )

    status: str
    message: str
    data: ConfirmSeatData
