"""Stage 2 — aggregation.

Nobody reads 200 rows; everybody reads five numbers. Every SQL statement the
report needs lives here, as a named constant, so it can be pasted into the
README and read on its own.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

# --- The aggregation queries -------------------------------------------------

TOTALS_SQL = """
SELECT COUNT(*)                    AS total_orders,
       COALESCE(SUM(amount), 0)    AS total_revenue,
       COALESCE(AVG(amount), 0)    AS average_order_value
FROM orders
WHERE date(created_at) >= :since
"""

TOP_PRODUCTS_SQL = """
SELECT product,
       COUNT(*)    AS orders,
       SUM(amount) AS revenue
FROM orders
WHERE date(created_at) >= :since
GROUP BY product
ORDER BY revenue DESC
LIMIT 5
"""

ORDERS_PER_DAY_SQL = """
SELECT date(created_at)  AS day,
       COUNT(*)          AS orders,
       SUM(amount)       AS revenue
FROM orders
WHERE date(created_at) >= :since
GROUP BY day
ORDER BY day
"""

ALL_ORDERS_SQL = """
SELECT id, customer, product, amount, created_at
FROM orders
WHERE date(created_at) >= :since
ORDER BY created_at DESC, id DESC
"""

COUNT_ORDERS_SQL = "SELECT COUNT(*) AS n FROM orders"


def _rows(conn: sqlite3.Connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def get_report_data(
    conn: sqlite3.Connection,
    *,
    days: int = 30,
    daily_window_days: int = 7,
    today: date | None = None,
) -> dict[str, Any]:
    """Turn rows into the four numbers-shaped sections the report is made of.

    ``days`` is the report window (default: the last 30 days). The per-day
    breakdown never looks further back than ``daily_window_days``.
    """
    today = today or date.today()
    since = today - timedelta(days=days - 1)
    daily_days = min(days, daily_window_days)
    daily_since = today - timedelta(days=daily_days - 1)

    totals = _rows(conn, TOTALS_SQL, {"since": since.isoformat()})[0]
    top_products = _rows(conn, TOP_PRODUCTS_SQL, {"since": since.isoformat()})
    per_day = {
        row["day"]: row
        for row in _rows(conn, ORDERS_PER_DAY_SQL, {"since": daily_since.isoformat()})
    }
    orders = _rows(conn, ALL_ORDERS_SQL, {"since": since.isoformat()})

    # Zero-fill quiet days so the table always shows a full window.
    orders_per_day = []
    for offset in range(daily_days):
        day = (daily_since + timedelta(days=offset)).isoformat()
        row = per_day.get(day)
        orders_per_day.append(
            {
                "day": day,
                "orders": row["orders"] if row else 0,
                "revenue": round(row["revenue"], 2) if row else 0.0,
            }
        )

    return {
        "generated_at": None,  # filled in by the renderer, kept out of the SQL layer
        "window": {"days": days, "since": since.isoformat(), "until": today.isoformat()},
        "totals": {
            "total_orders": totals["total_orders"],
            "total_revenue": round(totals["total_revenue"], 2),
            "average_order_value": round(totals["average_order_value"], 2),
        },
        "top_products": [
            {"product": r["product"], "orders": r["orders"], "revenue": round(r["revenue"], 2)}
            for r in top_products
        ],
        "orders_per_day": orders_per_day,
        "orders": orders,
    }


def count_orders(conn: sqlite3.Connection) -> int:
    return int(conn.execute(COUNT_ORDERS_SQL).fetchone()["n"])
