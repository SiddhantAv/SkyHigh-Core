from fastapi import APIRouter, status

from skyhigh.api.deps import DbSession, SeatServiceDep
from skyhigh.api.schemas.checkin import (
    ConfirmSeatApiResponse,
    ConfirmSeatRequest,
    HoldSeatApiResponse,
    HoldSeatRequest,
)
from skyhigh.api.schemas.errors import StructuredErrorBody

router = APIRouter(tags=["seats"])


@router.post(
    "/{seat_id}/hold",
    response_model=HoldSeatApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Hold a seat",
    description=(
        "Temporarily reserves a seat for **120 seconds** (configurable). "
        "Uses row-level locking so only one passenger can hold the same seat at a time. "
        "Repeat the same `idempotency_key` to safely retry after network issues."
    ),
    responses={
        404: {"model": StructuredErrorBody, "description": "Seat not found."},
        409: {
            "model": StructuredErrorBody,
            "description": "Seat unavailable, already confirmed, hold expired, or idempotency key reused for another seat.",
        },
    },
)
def hold_seat(
    seat_id: int,
    body: HoldSeatRequest,
    db: DbSession,
    svc: SeatServiceDep,
) -> HoldSeatApiResponse:
    data = svc.hold_seat(db, body.passenger_id, seat_id, body.idempotency_key)
    return HoldSeatApiResponse.model_validate(data)


@router.post(
    "/{seat_id}/confirm",
    response_model=ConfirmSeatApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm a held seat",
    description=(
        "Converts an active **HELD** seat to **CONFIRMED** for the same passenger "
        "before the hold expires. Idempotent via `idempotency_key`."
    ),
    responses={
        404: {"model": StructuredErrorBody, "description": "Seat not found."},
        409: {
            "model": StructuredErrorBody,
            "description": "Seat not held by passenger, hold expired, already confirmed, or idempotency key reused for another seat.",
        },
    },
)
def confirm_seat(
    seat_id: int,
    body: ConfirmSeatRequest,
    db: DbSession,
    svc: SeatServiceDep,
) -> ConfirmSeatApiResponse:
    data = svc.confirm_seat(db, body.passenger_id, seat_id, body.idempotency_key)
    return ConfirmSeatApiResponse.model_validate(data)
