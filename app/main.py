"""FastAPI application: one server, one browser, one SQLite file."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import connect, init_schema
from app.rendering import PdfRenderer
from app.routers import health, reports

logger = logging.getLogger("pdf-report-generator")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.resolved_reports_dir.mkdir(parents=True, exist_ok=True)

    conn = connect(settings.resolved_db_path)
    init_schema(conn)

    renderer = PdfRenderer(channel=settings.browser_channel)
    await renderer.start()
    logger.info("ready: db=%s reports=%s", settings.resolved_db_path, settings.resolved_reports_dir)

    app.state.settings = settings
    app.state.db = conn
    app.state.renderer = renderer
    try:
        yield
    finally:
        await renderer.stop()
        conn.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="PDF report generator",
        version="1.0.0",
        summary="Query SQLite, render HTML to PDF, serve the file by link.",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(reports.router)
    return app


app = create_app()
