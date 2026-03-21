from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthApiResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "message": "SkyHigh Core is running.",
                    "data": None,
                }
            ]
        }
    )

    status: str
    message: str
    data: dict[str, Any] | None = None


class ReadyApiResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ready",
                    "message": "Database and Redis are reachable.",
                    "data": {"database": "ok", "redis": "ok"},
                }
            ]
        }
    )

    status: str
    message: str
    data: dict[str, Any] | None = None
