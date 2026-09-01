"""Stage 3 — render: numbers -> HTML -> PDF.

You do not draw a PDF. You build a web page and ask a headless browser to print
it. Playwright drives Chromium; ``page.pdf()`` does the printing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import Browser, async_playwright

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Playwright draws these on every page — that is where page numbers come from
# (Chromium ignores CSS paged-media margin boxes).
HEADER_TEMPLATE = '<div style="width:100%"></div>'
FOOTER_TEMPLATE = """
<div style="width:100%;font:8px -apple-system,Helvetica,Arial,sans-serif;color:#64748b;
            padding:0 14mm;display:flex;justify-content:space-between;">
  <span>FlyRank &middot; Sales report</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>
"""


def _money(value: float | int | None) -> str:
    return "-" if value is None else f"EUR {float(value):,.2f}"


def build_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["money"] = _money
    return env


_env = build_environment()


def render_html(data: dict[str, Any], *, generated_at: datetime | None = None) -> str:
    """Fill the template with this report's numbers."""
    generated_at = generated_at or datetime.now()
    return _env.get_template("report.html.j2").render(
        data=data,
        title=f"Sales report — {generated_at:%d %B %Y}",
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M"),
    )


class PdfRenderer:
    """Owns one long-lived headless browser.

    Launching Chromium costs about a second; the API starts it once at boot and
    reuses it for every report instead of paying that on each request.
    """

    def __init__(self, channel: str | None = None) -> None:
        self._channel = channel or None
        self._playwright = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": True}
        if self._channel:  # e.g. PDF_BROWSER_CHANNEL=chrome to use the system Chrome
            launch_kwargs["channel"] = self._channel
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def render_pdf(self, html: str, path: Path) -> Path:
        if self._browser is None:
            raise RuntimeError("PdfRenderer.start() was never awaited")
        path.parent.mkdir(parents=True, exist_ok=True)
        # One page at a time: a browser context per render keeps state isolated.
        async with self._lock:
            page = await self._browser.new_page()
            try:
                await page.set_content(html, wait_until="load")
                await page.pdf(
                    path=str(path),
                    format="A4",
                    print_background=True,
                    display_header_footer=True,
                    header_template=HEADER_TEMPLATE,
                    footer_template=FOOTER_TEMPLATE,
                    margin={"top": "18mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
                )
            finally:
                await page.close()
        return path

    async def __aenter__(self) -> "PdfRenderer":
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()
