from pydantic import BaseModel, ConfigDict, Field


class SeatMapRow(BaseModel):
    seat_id: int
    seat_number: str
    status: str


class SeatMapData(BaseModel):
    flight_id: int
    seats: list[SeatMapRow]


class SeatMapApiResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "success",
                    "message": "Seat map retrieved successfully.",
                    "data": {
                        "flight_id": 1,
                        "seats": [
                            {"seat_id": 1, "seat_number": "1A", "status": "AVAILABLE"},
                            {"seat_id": 2, "seat_number": "1B", "status": "HELD"},
                        ],
                    },
                }
            ]
        }
    )

    status: str = Field(default="success")
    message: str
    data: SeatMapData
