"""Stage 2 checkpoint — print the report object as JSON.

    python -m scripts.print_report --days 30
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import session  # noqa: E402
from app.queries import get_report_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the aggregated report as JSON.")
    parser.add_argument("--days", type=int, default=None, help="report window in days")
    parser.add_argument("--full", action="store_true", help="include the long orders list")
    args = parser.parse_args()

    settings = get_settings()
    days = args.days or settings.default_report_days
    with session(settings.resolved_db_path) as conn:
        data = get_report_data(
            conn, days=days, daily_window_days=settings.daily_window_days
        )

    if not args.full:
        data["orders"] = f"<{len(data['orders'])} rows — pass --full to print them>"
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()
