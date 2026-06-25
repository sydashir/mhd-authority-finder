"""Typed application settings loaded from ``.env`` via pydantic-settings.

All runtime configuration funnels through :class:`Settings`. Modules should never
read ``os.environ`` directly — they take a ``Settings`` instance (or a narrow
slice of it) at construction time so config is explicit and testable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime configuration. Values are sourced from ``.env`` then environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    serpapi_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="SerpAPI key for per-geo search discovery.",
    )
    ahrefs_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Ahrefs API key for Domain Rating lookups (Phase 2).",
    )
    census_api_key: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "US Census API key. Census retired keyless access (May 2026, ADR-008); "
            "a free key is required for population — without it lookups return not_found."
        ),
    )

    google_sheets_credentials_path: Path = Field(
        default=Path("service-account.json"),
        description="Path to the Google service-account JSON used to write the output sheet.",
    )
    google_sheet_id: str = Field(
        default="",
        description="Target Google Sheet ID (the long token in the sheet URL).",
    )

    ahrefs_dr_threshold: int = Field(
        default=40,
        ge=0,
        le=100,
        description="Minimum Domain Rating for a non-.gov/.edu site to be retained.",
    )

    run_interval_hours: int = Field(
        default=24,
        ge=1,
        description="Scheduler interval between incremental runs (RUN_INTERVAL_HOURS).",
    )
    max_new_geos_per_run: int = Field(
        default=25,
        ge=1,
        description=(
            "Cap on new geos processed per scheduled run (MAX_NEW_GEOS_PER_RUN). Overflow is "
            "deferred to the next tick so a site re-publishing its sitemap can't blow quota."
        ),
    )
    max_billed_searches_per_run: int = Field(
        default=150,
        ge=1,
        description=(
            "Circuit breaker: abort a run once it has spent this many billed SerpAPI searches "
            "(MAX_BILLED_SEARCHES_PER_RUN)."
        ),
    )

    playwright_no_sandbox: bool = Field(
        default=False,
        description=(
            "Launch headless Chromium with --no-sandbox (PLAYWRIGHT_NO_SANDBOX). Required in "
            "containers where the setuid sandbox can't initialize; leave off on a normal host."
        ),
    )

    log_level: LogLevel = Field(
        default="INFO",
        description="Root log level for structlog and the stdlib logging shim.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings``. Cheap to call from anywhere."""
    return Settings()
