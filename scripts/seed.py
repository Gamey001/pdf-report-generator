"""Stage 1 — seed data.

Creates report.db and fills it with ~200 random orders. Safe to run twice: the
script clears the table first, so a second run leaves exactly one clean copy.

    python -m scripts.seed            # 200 orders
    python -m scripts.seed --orders 5000
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import session  # noqa: E402
from app.queries import count_orders  # noqa: E402

PRODUCTS = [
    "Sky Blue Backpack",
    "Trail Runner Shoes",
    "Merino Beanie",
    "Rain Shell Jacket",
    "Canvas Sneakers",
    "Insulated Bottle",
]

CUSTOMERS = [
    "Ada Lovelace", "Grace Hopper", "Alan Turing", "Katherine Johnson",
    "Linus Torvalds", "Barbara Liskov", "Ken Thompson", "Radia Perlman",
    "Margaret Hamilton", "Donald Knuth", "Anita Borg", "Tim Berners-Lee",
]


def clear_orders(conn: sqlite3.Connection) -> None:
    """Running the seed twice must not double the row count."""
    with conn:
        conn.execute("DELETE FROM orders")


def insert_orders(conn: sqlite3.Connection, count: int, span_days: int, seed: int | None) -> None:
    rng = random.Random(seed)
    now = datetime.now()
    rows = []
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(count):
        # A random day inside the window, at a random time of that day — never
        # in the future, so every seeded order lands inside the report window.
        day = midnight - timedelta(days=rng.randrange(span_days))
        seconds_in_day = 86_400 if day < midnight else max(int((now - midnight).total_seconds()), 1)
        moment = day + timedelta(seconds=rng.randrange(seconds_in_day))
        rows.append(
            (
                rng.choice(CUSTOMERS),
                rng.choice(PRODUCTS),
                round(rng.uniform(5, 200), 2),
                moment.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
    with conn:
        conn.executemany(
            "INSERT INTO orders (customer, product, amount, created_at) VALUES (?, ?, ?, ?)",
            rows,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed report.db with random orders.")
    parser.add_argument("--orders", type=int, default=200, help="how many orders to insert")
    parser.add_argument("--days", type=int, default=30, help="spread orders over the last N days")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible data")
    args = parser.parse_args()

    settings = get_settings()
    with session(settings.resolved_db_path) as conn:
        clear_orders(conn)
        insert_orders(conn, args.orders, args.days, args.seed)
        total = count_orders(conn)

    print(f"Seeded {args.orders} orders into {settings.resolved_db_path}")
    print(f"SELECT COUNT(*) FROM orders -> {total}")


if __name__ == "__main__":
    main()
