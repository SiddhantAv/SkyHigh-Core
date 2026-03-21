from fastapi import APIRouter, status

from skyhigh.api.deps import DbSession, SeatServiceDep
from skyhigh.api.schemas.errors import StructuredErrorBody
from skyhigh.api.schemas.flights import SeatMapApiResponse, SeatMapData, SeatMapRow

router = APIRouter(tags=["flights"])


@router.get(
    "/{flight_id}/seats",
    response_model=SeatMapApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Get seat map for a flight",
    description=(
        "Returns all seats for a flight. Responses are cached in Redis for a short TTL "
        "for high read throughput; cache is invalidated on seat changes."
    ),
    responses={
        500: {
            "model": StructuredErrorBody,
            "description": "Unexpected failure (cache failures fall back to DB).",
        },
    },
)
def get_flight_seat_map(
    flight_id: int,
    db: DbSession,
    svc: SeatServiceDep,
) -> SeatMapApiResponse:
    rows = svc.get_seat_map(db, flight_id)
    return SeatMapApiResponse(
        status="success",
        message="Seat map retrieved successfully.",
        data=SeatMapData(
            flight_id=flight_id,
            seats=[SeatMapRow.model_validate(r) for r in rows],
        ),
    )
