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
        description="US Census Bureau API key for population lookups.",
    )

    google_sheets_credentials_path: Path = Field(
        default=Path("credentials.json"),
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

    log_level: LogLevel = Field(
        default="INFO",
        description="Root log level for structlog and the stdlib logging shim.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings``. Cheap to call from anywhere."""
    return Settings()
