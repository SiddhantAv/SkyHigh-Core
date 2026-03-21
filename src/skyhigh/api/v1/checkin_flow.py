from fastapi import APIRouter, status

from skyhigh.api.deps import CheckinServiceDep, DbSession
from skyhigh.api.schemas.checkin_flow import (
    CheckinCompleteRequest,
    CheckinCompleteResponse,
    CheckinStartRequest,
    CheckinStartResponse,
    PaymentCompleteResponse,
    PaymentRequest,
)
from skyhigh.api.schemas.errors import StructuredErrorBody

router = APIRouter(tags=["check-in"])


@router.post(
    "/start",
    response_model=CheckinStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start check-in",
    description=(
        "Begins check-in for a **confirmed** seat that belongs to the passenger. "
        "Within the baggage limit, status is **IN_PROGRESS** until `POST /checkin/complete`. "
        "Over the limit (default 25 kg), status is **WAITING_FOR_PAYMENT** until "
        "`POST /checkin/payment` (simulated)."
    ),
    responses={
        409: {
            "model": StructuredErrorBody,
            "description": "Seat not confirmed for passenger, missing, or other check-in rule violation.",
        },
    },
)
def start_checkin(
    body: CheckinStartRequest,
    db: DbSession,
    svc: CheckinServiceDep,
) -> CheckinStartResponse:
    data = svc.start_checkin(db, body.passenger_id, body.seat_id, body.baggage_weight)
    return CheckinStartResponse.model_validate(data)


@router.post(
    "/complete",
    response_model=CheckinCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete check-in (within baggage limit)",
    description=(
        "Finishes check-in when the session is **IN_PROGRESS** (baggage already within limit). "
        "If the session is **WAITING_FOR_PAYMENT**, use `POST /checkin/payment` instead."
    ),
    responses={
        409: {
            "model": StructuredErrorBody,
            "description": "Seat not confirmed, wrong passenger, wrong session state, or payment required first.",
        },
    },
)
def complete_checkin(
    body: CheckinCompleteRequest,
    db: DbSession,
    svc: CheckinServiceDep,
) -> CheckinCompleteResponse:
    data = svc.complete_checkin(db, body.passenger_id, body.seat_id)
    return CheckinCompleteResponse.model_validate(data)


@router.post(
    "/payment",
    response_model=PaymentCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete extra baggage payment (simulated)",
    description=(
        "Marks the extra-baggage fee as **paid** and completes the check-in session. "
        "Only valid when the session is in `WAITING_FOR_PAYMENT`."
    ),
    responses={
        404: {"model": StructuredErrorBody, "description": "Check-in session not found."},
        409: {
            "model": StructuredErrorBody,
            "description": "Session is not waiting for payment.",
        },
    },
)
def complete_checkin_payment(
    body: PaymentRequest,
    db: DbSession,
    svc: CheckinServiceDep,
) -> PaymentCompleteResponse:
    data = svc.complete_payment(db, body.checkin_session_id)
    return PaymentCompleteResponse.model_validate(data)
