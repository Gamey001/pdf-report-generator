"""Stage 3 checkpoint — render the report straight to reports/test.pdf.

    python -m scripts.render_pdf
    python -m scripts.render_pdf --out reports/test.pdf --days 30
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import session  # noqa: E402
from app.queries import get_report_data  # noqa: E402
from app.rendering import PdfRenderer, render_html  # noqa: E402


async def render(out: Path, days: int) -> Path:
    settings = get_settings()
    with session(settings.resolved_db_path) as conn:
        data = get_report_data(
            conn, days=days, daily_window_days=settings.daily_window_days
        )
    html = render_html(data, generated_at=datetime.now())
    async with PdfRenderer(channel=settings.browser_channel) as renderer:
        return await renderer.render_pdf(html, out)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Render the report to a PDF file.")
    parser.add_argument("--out", type=Path, default=settings.resolved_reports_dir / "test.pdf")
    parser.add_argument("--days", type=int, default=settings.default_report_days)
    args = parser.parse_args()

    path = asyncio.run(render(args.out, args.days))
    print(f"Wrote {path} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
