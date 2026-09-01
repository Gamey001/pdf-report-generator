"""Application settings.

Everything that could differ between machines (paths, port) lives here and can be
overridden with environment variables, e.g. ``DB_PATH=/tmp/report.db``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where the SQLite file lives. One file, no server to run.
    db_path: Path = BASE_DIR / "report.db"

    # Where generated PDFs are stored. Artifacts live on disk, never in JSON.
    reports_dir: Path = BASE_DIR / "reports"

    # Default report window, in days, when the client does not ask for one.
    default_report_days: int = 30

    # The "orders per day" section never looks further back than this.
    daily_window_days: int = 7

    # Leave empty to use Playwright's bundled Chromium (the normal case). Set to
    # "chrome" to drive the system Chrome instead — handy on older macOS builds
    # that Playwright no longer ships a Chromium download for.
    browser_channel: str = ""

    @property
    def resolved_db_path(self) -> Path:
        return self.db_path if self.db_path.is_absolute() else BASE_DIR / self.db_path

    @property
    def resolved_reports_dir(self) -> Path:
        return self.reports_dir if self.reports_dir.is_absolute() else BASE_DIR / self.reports_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
