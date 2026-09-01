"""SQLite access: connections and the orders table.

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
