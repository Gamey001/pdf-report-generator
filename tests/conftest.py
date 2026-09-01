from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import session  # noqa: E402
from app.rendering import PdfRenderer  # noqa: E402

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    """A tiny, hand-made dataset with numbers we can assert on exactly."""
    db_path = tmp_path / "report.db"
    today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    rows = [
        ("Ada", "Backpack", 100.0, today),
        ("Ada", "Backpack", 50.0, today - timedelta(days=1)),
        ("Grace", "Beanie", 25.0, today - timedelta(days=2)),
        ("Alan", "Bottle", 75.0, today - timedelta(days=6)),
        ("Alan", "Bottle", 25.0, today - timedelta(days=20)),
        ("Linus", "Jacket", 10.0, today - timedelta(days=200)),  # outside every window
    ]
    with session(db_path) as conn:
        with conn:
            conn.executemany(
                "INSERT INTO orders (customer, product, amount, created_at) VALUES (?, ?, ?, ?)",
                [(c, p, a, m.strftime("%Y-%m-%d %H:%M:%S")) for c, p, a, m in rows],
            )
    return db_path


@pytest.fixture
def app_env(seeded_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    reports_dir = tmp_path / "reports"
    monkeypatch.setenv("DB_PATH", str(seeded_db))
    monkeypatch.setenv("REPORTS_DIR", str(reports_dir))
    get_settings.cache_clear()
    yield reports_dir
    get_settings.cache_clear()


@pytest.fixture
def fake_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the API tests fast: no real Chromium, just a file on disk."""

    async def start(self: PdfRenderer) -> None:
        return None

    async def stop(self: PdfRenderer) -> None:
        return None

    async def render_pdf(self: PdfRenderer, html: str, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MINIMAL_PDF)
        return path

    monkeypatch.setattr(PdfRenderer, "start", start)
    monkeypatch.setattr(PdfRenderer, "stop", stop)
    monkeypatch.setattr(PdfRenderer, "render_pdf", render_pdf)


@pytest.fixture
def client(app_env: Path, fake_browser: None) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

