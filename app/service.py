"""Stages 4 & 5 — the pipeline behind POST /reports.

query -> render -> store -> hand back a link. And: asking twice on the same day
gives you the same report, not a second file.
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.queries import get_report_data
from app.rendering import PdfRenderer, render_html

# Serialises generation inside this process; the UNIQUE index on
# (report_date, params_key) is the durable guarantee behind it.
_generation_lock = asyncio.Lock()


@dataclass(frozen=True)
class Report:
    id: int
    path: str
    created_at: str
    report_date: str
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
            "report_date": self.report_date,
            "days": self.days,
        }

    def to_response(self, *, reused: bool) -> dict[str, Any]:
        return {**self.to_record(), "reused": reused}


def params_key(days: int) -> str:
    """Two requests with the same parameters are the same report."""
    return f"days={days}"


def _row_to_report(row: sqlite3.Row | None) -> Report | None:
    if row is None or row["path"] is None:
        return None
    return Report(
        id=row["id"],
        path=row["path"],
        created_at=row["created_at"],
        report_date=row["report_date"],
        days=row["days"],
    )


def get_report(conn: sqlite3.Connection, report_id: int) -> Report | None:
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return _row_to_report(row)


def list_reports(conn: sqlite3.Connection, limit: int = 50) -> list[Report]:
    rows = conn.execute(
        "SELECT * FROM reports WHERE path IS NOT NULL ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [report for report in map(_row_to_report, rows) if report is not None]


def find_todays_report(conn: sqlite3.Connection, *, days: int, today: date) -> Report | None:
    """The current report for this day and these parameters, if there is one."""
    row = conn.execute(
        """
        SELECT * FROM reports
        WHERE report_date = ? AND params_key = ? AND superseded_at IS NULL
        """,
        (today.isoformat(), params_key(days)),
    ).fetchone()
    return _row_to_report(row)


def _supersede_current(
    conn: sqlite3.Connection, *, days: int, today: date, now: datetime
) -> int | None:
    """Retire today's report so force=true can take its slot. Returns its id."""
    current = find_todays_report(conn, days=days, today=today)
    if current is None:
        return None
    with conn:
        conn.execute(
            "UPDATE reports SET superseded_at = ? WHERE id = ?",
            (now.strftime("%Y-%m-%d %H:%M:%S"), current.id),
        )
    return current.id


def _restore_superseded(conn: sqlite3.Connection, report_id: int) -> None:
    with conn:
        conn.execute("UPDATE reports SET superseded_at = NULL WHERE id = ?", (report_id,))


def _claim_report_row(conn: sqlite3.Connection, *, days: int, now: datetime) -> int:
    """Reserve an id (and the day+params slot) before the slow work starts."""
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (path, created_at, report_date, days, params_key)
            VALUES (NULL, ?, ?, ?, ?)
            """,
            (
                now.strftime("%Y-%m-%d %H:%M:%S"),
                now.date().isoformat(),
                days,
                params_key(days),
            ),
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
    force: bool = False,
    daily_window_days: int = 7,
    now: datetime | None = None,
) -> tuple[Report, bool]:
    """Run the pipeline. Returns ``(report, created)``.

    ``created`` is False when an existing report for today was reused — that is
    Stage 5's "ask twice, get one".
    """
    now = now or datetime.now()
    today = now.date()

    async with _generation_lock:
        if not force:
            existing = await run_in_threadpool(find_todays_report, conn, days=days, today=today)
            if existing is not None:
                return existing, False

        # force=True must be able to take today's slot. The old report is retired,
        # not deleted: its file stays on disk so links already handed out still work.
        superseded_id = None
        if force:
            superseded_id = await run_in_threadpool(
                _supersede_current, conn, days=days, today=today, now=now
            )

        report_id = await run_in_threadpool(_claim_report_row, conn, days=days, now=now)
        path = reports_dir / _report_filename(report_id, today)
        try:
            data = await run_in_threadpool(
                get_report_data,
                conn,
                days=days,
                daily_window_days=daily_window_days,
                today=today,
            )
            html = render_html(data, generated_at=now)
            await renderer.render_pdf(html, path)
            await run_in_threadpool(_finish_report_row, conn, report_id, path)
        except Exception:
            # A half-generated report must not occupy today's slot — and a failed
            # force must not leave the day without a current report.
            await run_in_threadpool(_discard_report_row, conn, report_id)
            path.unlink(missing_ok=True)
            if superseded_id is not None:
                await run_in_threadpool(_restore_superseded, conn, superseded_id)
            raise

    return (
        Report(
            id=report_id,
            path=str(path),
            created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
            report_date=today.isoformat(),
            days=days,
        ),
        True,
    )
