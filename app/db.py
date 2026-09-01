"""SQLite access: connections, schema, and the report bookkeeping table.

SQLite is built into Python (``sqlite3``), so there is nothing to install and the
whole database is a single file on disk.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY,
    customer   TEXT    NOT NULL,
    product    TEXT    NOT NULL,
    amount     REAL    NOT NULL,
    created_at TEXT    NOT NULL              -- 'YYYY-MM-DD HH:MM:SS'
);

CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders(created_at);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- ids are never recycled
    path          TEXT,                      -- filled in once the PDF is on disk
    created_at    TEXT    NOT NULL,          -- 'YYYY-MM-DD HH:MM:SS'
    report_date   TEXT    NOT NULL,          -- 'YYYY-MM-DD', the day it was generated
    days          INTEGER NOT NULL,          -- the report window that was requested
    params_key    TEXT    NOT NULL,          -- canonical form of the request parameters
    superseded_at TEXT                       -- set when force=true replaced this one
);

-- The durable half of Stage 5: the database itself refuses a second *current*
-- report for the same day and the same parameters, even if two requests race.
-- Superseded rows stay behind so old links keep working.
CREATE UNIQUE INDEX IF NOT EXISTS ux_reports_day_params
    ON reports(report_date, params_key) WHERE superseded_at IS NULL;
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with sane defaults (dict-like rows, FK enforcement)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(SCHEMA)


@contextmanager
def session(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Short-lived connection for scripts and tests."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        yield conn
    finally:
        conn.close()
