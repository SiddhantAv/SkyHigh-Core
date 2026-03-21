"""Documented API error shape (used in OpenAPI `responses`)."""

from pydantic import BaseModel, Field


class StructuredErrorBody(BaseModel):
    error: str = Field(..., description="Stable machine-readable error code.")
    message: str = Field(..., description="User-safe explanation.")
    details: dict | None = Field(None, description="Optional structured context.")
