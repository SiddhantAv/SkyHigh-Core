from pydantic import BaseModel, ConfigDict, Field


class CheckinStartRequest(BaseModel):
    passenger_id: int = Field(..., ge=1, examples=[1])
    seat_id: int = Field(..., ge=1, examples=[12])
    baggage_weight: float = Field(..., ge=0, examples=[30.0], description="Total baggage weight in kilograms.")


class CheckinStartData(BaseModel):
    checkin_session_id: int
    baggage_weight: float | None = None


class CheckinStartResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "IN_PROGRESS",
                    "message": "Check-in started. Baggage is within the allowed 25 kg. Call POST /checkin/complete.",
                    "data": {"checkin_session_id": 4, "baggage_weight": 18.0},
                },
                {
                    "status": "WAITING_FOR_PAYMENT",
                    "message": "Baggage exceeds 25 kg. Please complete payment to continue check-in.",
                    "data": {"checkin_session_id": 5, "baggage_weight": 30.0},
                },
            ]
        }
    )

    status: str
    message: str
    data: CheckinStartData


class PaymentRequest(BaseModel):
    checkin_session_id: int = Field(..., ge=1, examples=[5])


class CheckinCompleteRequest(BaseModel):
    passenger_id: int = Field(..., ge=1, examples=[1])
    seat_id: int = Field(..., ge=1, examples=[12])


class CheckinCompleteResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "COMPLETED",
                    "message": "Check-in completed.",
                    "data": {"checkin_session_id": 4, "baggage_weight": 18.0},
                }
            ]
        }
    )

    status: str
    message: str
    data: CheckinStartData


class PaymentCompleteData(BaseModel):
    checkin_session_id: int


class PaymentCompleteResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "COMPLETED",
                    "message": "Payment successful. Check-in completed.",
                    "data": {"checkin_session_id": 5},
                }
            ]
        }
    )

    status: str
    message: str
    data: PaymentCompleteData
