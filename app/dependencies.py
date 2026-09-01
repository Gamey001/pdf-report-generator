"""Shared resources: one SQLite connection and one browser, both app-scoped."""

from __future__ import annotations

import sqlite3

from fastapi import Request

from app.config import Settings
from app.rendering import PdfRenderer


def get_db(request: Request) -> sqlite3.Connection:
    return request.app.state.db


def get_renderer(request: Request) -> PdfRenderer:
    return request.app.state.renderer


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
