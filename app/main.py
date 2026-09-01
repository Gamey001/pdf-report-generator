"""FastAPI application — Stage 0: a server with one endpoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health

logger = logging.getLogger("pdf-report-generator")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.resolved_reports_dir.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings
    logger.info("ready: db=%s reports=%s", settings.resolved_db_path, settings.resolved_reports_dir)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="PDF report generator",
        version="0.1.0",
        summary="Query SQLite, render HTML to PDF, serve the file by link.",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    return app


app = create_app()
