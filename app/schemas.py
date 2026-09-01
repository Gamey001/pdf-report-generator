"""Request and response models — the API's contract, in one place."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class GenerateReportRequest(BaseModel):
    days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Report window in days, counting back from today.",
    )


class ReportRecord(BaseModel):
    """What the API knows about one generated report — an address, not bytes."""

    id: int
    file: str = Field(description="Link to download the PDF — the bytes stay on disk.")
    filename: str
    created_at: str
    days: int


class ReportResponse(ReportRecord):
    pass


class ErrorResponse(BaseModel):
    detail: str
