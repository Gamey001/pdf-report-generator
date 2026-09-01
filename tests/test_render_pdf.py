"""Stage 3 — the promise the PDF itself has to keep.

Slow: this one launches a real headless Chromium. Run it with `pytest -m slow`.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import session  # noqa: E402
from scripts.seed import insert_orders  # noqa: E402

pytestmark = pytest.mark.slow


@pytest.fixture
def big_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "report.db"
    with session(db_path) as conn:
        insert_orders(conn, count=200, span_days=30, seed=7)
    return db_path


@pytest.fixture
def real_client(
    big_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("DB_PATH", str(big_db))
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "reports"))
    get_settings.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_generated_pdf_is_multi_page_with_a_repeating_header(real_client: TestClient) -> None:
    pypdf = pytest.importorskip("pypdf")

    body = real_client.post("/reports").json()
    pdf_path = get_settings().resolved_reports_dir / body["filename"]
    reader = pypdf.PdfReader(pdf_path)

    assert len(reader.pages) >= 2, "200 orders should not fit on one page"

    ledger_pages = [
        (page.extract_text() or "").upper()
        for page in reader.pages
        if "EUR" in (page.extract_text() or "")
    ]
    ledger_pages = ledger_pages[1:]  # skip the summary page
    assert ledger_pages, "expected pages of the long orders table"
    assert all("CUSTOMER" in text for text in ledger_pages), (
        "the table header must repeat on every page of the long table"
    )
