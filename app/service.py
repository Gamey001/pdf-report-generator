"""Stage 4 — the pipeline behind POST /reports.

query -> render -> store -> hand back a link. It all happens inside the request,
which is exactly why the response takes a moment.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.queries import get_report_data
from app.rendering import PdfRenderer, render_html


@dataclass(frozen=True)
class Report:
    id: int
    path: str
    created_at: str
    days: int

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def file_url(self) -> str:
        return f"/reports/{self.id}/file"

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file": self.file_url,
            "filename": self.filename,
            "created_at": self.created_at,
            "days": self.days,
        }


def _row_to_report(row: sqlite3.Row | None) -> Report | None:
    if row is None or row["path"] is None:
        return None
    return Report(
        id=row["id"], path=row["path"], created_at=row["created_at"], days=row["days"]
    )


def get_report(conn: sqlite3.Connection, report_id: int) -> Report | None:
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return _row_to_report(row)


def list_reports(conn: sqlite3.Connection, limit: int = 50) -> list[Report]:
    rows = conn.execute(
        "SELECT * FROM reports WHERE path IS NOT NULL ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [report for report in map(_row_to_report, rows) if report is not None]


def _claim_report_row(conn: sqlite3.Connection, *, days: int, now: datetime) -> int:
    """Reserve an id before the slow work starts."""
    with conn:
        cursor = conn.execute(
            "INSERT INTO reports (path, created_at, days) VALUES (NULL, ?, ?)",
            (now.strftime("%Y-%m-%d %H:%M:%S"), days),
        )
    return int(cursor.lastrowid)


def _finish_report_row(conn: sqlite3.Connection, report_id: int, path: Path) -> None:
    with conn:
        conn.execute("UPDATE reports SET path = ? WHERE id = ?", (str(path), report_id))


def _discard_report_row(conn: sqlite3.Connection, report_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))


def _report_filename(report_id: int, day: date) -> str:
    return f"sales-report-{day.isoformat()}-{report_id}.pdf"


async def generate_report(
    conn: sqlite3.Connection,
    renderer: PdfRenderer,
    reports_dir: Path,
    *,
    days: int,
    daily_window_days: int = 7,
    now: datetime | None = None,
) -> Report:
    """Run the whole pipeline, right here in the request."""
    now = now or datetime.now()
    today = now.date()

    report_id = await run_in_threadpool(_claim_report_row, conn, days=days, now=now)
    path = reports_dir / _report_filename(report_id, today)
    try:
        data = await run_in_threadpool(
            get_report_data, conn, days=days, daily_window_days=daily_window_days, today=today
        )
        html = render_html(data, generated_at=now)
        await renderer.render_pdf(html, path)
        await run_in_threadpool(_finish_report_row, conn, report_id, path)
    except Exception:
        await run_in_threadpool(_discard_report_row, conn, report_id)
        path.unlink(missing_ok=True)
        raise

    return Report(
        id=report_id,
        path=str(path),
        created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        days=days,
    )
