"""Stage 4 — generate a report, look it up, download it.

Only ``GET /reports/{id}/file`` moves megabytes; every other response is a few
bytes of JSON carrying the file's address. That is "store and link".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.config import Settings
from app.dependencies import get_app_settings, get_db, get_renderer
from app.rendering import PdfRenderer
from app.schemas import GenerateReportRequest, ReportRecord, ReportResponse
from app.service import generate_report, get_report, list_reports

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report",
)
async def create_report(
    payload: GenerateReportRequest | None = None,
    conn: sqlite3.Connection = Depends(get_db),
    renderer: PdfRenderer = Depends(get_renderer),
    settings: Settings = Depends(get_app_settings),
) -> ReportResponse:
    payload = payload or GenerateReportRequest()
    report = await generate_report(
        conn,
        renderer,
        settings.resolved_reports_dir,
        days=payload.days,
        daily_window_days=settings.daily_window_days,
    )
    return ReportResponse(**report.to_record())


@router.get("", response_model=list[ReportRecord], summary="List generated reports")
async def index(conn: sqlite3.Connection = Depends(get_db)) -> list[ReportRecord]:
    return [ReportRecord(**r.to_record()) for r in list_reports(conn)]


@router.get("/{report_id}", response_model=ReportRecord, summary="One report's record")
async def show(report_id: int, conn: sqlite3.Connection = Depends(get_db)) -> ReportRecord:
    report = get_report(conn, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return ReportRecord(**report.to_record())


@router.get(
    "/{report_id}/file",
    response_class=FileResponse,
    summary="Download the PDF from disk",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download(report_id: int, conn: sqlite3.Connection = Depends(get_db)) -> FileResponse:
    report = get_report(conn, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    path = Path(report.path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"File for report {report_id} is missing")

    return FileResponse(path, media_type="application/pdf", filename=report.filename)
