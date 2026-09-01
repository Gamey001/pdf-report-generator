"""Stages 0, 4 and 5 — the API contract."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_generates_and_returns_a_link(client: TestClient, app_env: Path) -> None:
    response = client.post("/reports")
    assert response.status_code == 201

    body = response.json()
    assert body["file"] == f"/reports/{body['id']}/file"
    assert body["reused"] is False
    assert len(list(app_env.glob("*.pdf"))) == 1


def test_json_never_carries_the_bytes(client: TestClient) -> None:
    body = client.post("/reports").json()
    record = client.get(f"/reports/{body['id']}").json()
    assert set(record) == {"id", "file", "filename", "created_at", "report_date", "days"}


def test_unknown_report_is_404(client: TestClient) -> None:
    assert client.get("/reports/999").status_code == 404
    assert client.get("/reports/999/file").status_code == 404


def test_download_serves_the_pdf_from_disk(client: TestClient) -> None:
    body = client.post("/reports").json()
    response = client.get(body["file"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert body["filename"] in response.headers["content-disposition"]


def test_asking_twice_makes_one_report(client: TestClient, app_env: Path) -> None:
    first = client.post("/reports")
    second = client.post("/reports")

    assert first.status_code == 201
    assert second.status_code == 200                      # already existed
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["reused"] is True
    assert len(list(app_env.glob("*.pdf"))) == 1          # exactly one new file


def test_force_makes_a_fresh_report(client: TestClient, app_env: Path) -> None:
    first = client.post("/reports").json()
    forced = client.post("/reports", json={"force": True})

    assert forced.status_code == 201
    assert forced.json()["id"] != first["id"]
    assert len(list(app_env.glob("*.pdf"))) == 2
    # The replaced report is retired, not deleted: its link still works.
    assert client.get(first["file"]).status_code == 200
    # And the next plain POST reuses the forced one, not the retired one.
    assert client.post("/reports").json()["id"] == forced.json()["id"]


def test_different_windows_are_different_reports(client: TestClient) -> None:
    seven = client.post("/reports", json={"days": 7})
    thirty = client.post("/reports", json={"days": 30})

    assert seven.status_code == 201
    assert thirty.status_code == 201
    assert seven.json()["id"] != thirty.json()["id"]


def test_invalid_window_is_rejected(client: TestClient) -> None:
    assert client.post("/reports", json={"days": 0}).status_code == 422


def test_index_lists_reports(client: TestClient) -> None:
    client.post("/reports")
    listing = client.get("/reports").json()
    assert len(listing) == 1
