"""Stage 2 — the aggregations have to be right, or the PDF is a pretty lie."""

from __future__ import annotations

from pathlib import Path

from app.db import session
from app.queries import get_report_data


def test_totals_cover_only_the_window(seeded_db: Path) -> None:
    with session(seeded_db) as conn:
        data = get_report_data(conn, days=30)

    assert data["totals"]["total_orders"] == 5           # the 200-day-old row is excluded
    assert data["totals"]["total_revenue"] == 275.0
    assert data["totals"]["average_order_value"] == 55.0


def test_top_products_are_ranked_by_revenue(seeded_db: Path) -> None:
    with session(seeded_db) as conn:
        data = get_report_data(conn, days=30)

    top = data["top_products"]
    assert [row["product"] for row in top] == ["Backpack", "Bottle", "Beanie"]
    assert top[0] == {"product": "Backpack", "orders": 2, "revenue": 150.0}
    assert len(top) <= 5
    # A single product can never out-earn the whole report.
    assert top[0]["revenue"] <= data["totals"]["total_revenue"]


def test_orders_per_day_is_zero_filled(seeded_db: Path) -> None:
    with session(seeded_db) as conn:
        data = get_report_data(conn, days=30, daily_window_days=7)

    days = data["orders_per_day"]
    assert len(days) == 7
    assert [row["day"] for row in days] == sorted(row["day"] for row in days)
    assert days[-1]["orders"] == 1                       # today
    assert any(row["orders"] == 0 for row in days)       # quiet days still appear


def test_short_window_shrinks_everything(seeded_db: Path) -> None:
    with session(seeded_db) as conn:
        data = get_report_data(conn, days=2, daily_window_days=7)

    assert data["totals"]["total_orders"] == 2
    assert len(data["orders_per_day"]) == 2              # never longer than the window
    assert len(data["orders"]) == 2
