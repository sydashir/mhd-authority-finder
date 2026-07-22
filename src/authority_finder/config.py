"""Typed application settings loaded from ``.env`` via pydantic-settings.

All runtime configuration funnels through :class:`Settings`. Modules should never
read ``os.environ`` directly — they take a ``Settings`` instance (or a narrow
slice of it) at construction time so config is explicit and testable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    export_sheet_id: str = Field(
        default="",
        description=(
            "Workbook the UI's 'Export to Google Sheet' writes a NEW tab into (EXPORT_SHEET_ID). "
            "A plain service account can't create standalone spreadsheets, so exports add a tab to "
            "a workbook it can edit. Defaults to GOOGLE_SHEET_ID; the auto-write tab (Sheet1) is "
            "never touched. Point this at a dedicated workbook to keep exports out of the master."
        ),
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

    database_url: str = Field(
        default="postgresql+psycopg://authority:authority@localhost:5433/authority",
        description=(
            "Postgres source-of-truth (ADR-013). psycopg 3 URL (`+psycopg`) — one driver for the "
            "async app and sync Alembic. Default targets docker-compose postgres on localhost:5433."
        ),
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
    max_billed_searches_per_day: int = Field(
        default=320,
        ge=1,
        description=(
            "Global daily SerpAPI ceiling (MAX_BILLED_SEARCHES_PER_DAY, ADR-025). A run is refused "
            "when the last 24h of recorded runs have already spent this many billed searches — so "
            "no run flood (API triggers or the scheduler) can silently overspend the budget. "
            "Enforced against the runs table by the API, the scheduler, and the DB-persisting CLI."
        ),
    )

    cors_allow_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description=(
            "Browser origins the backend API allows (CORS_ALLOW_ORIGINS, JSON list). The Phase C "
            "React dev server (Vite 5173 / CRA 3000) by default; set the deployed origin in prod. "
            "allow_credentials is on, so this must be explicit origins, never '*'."
        ),
    )

    sentry_dsn: str = Field(
        default="",
        description=(
            "Sentry DSN for error monitoring (ADR-023). BLANK = monitoring disabled, so local dev "
            "is silent. Set only in production."
        ),
    )
    sentry_environment: str = Field(
        default="production",
        description="Sentry environment tag (SENTRY_ENVIRONMENT) — 'production' / 'staging'.",
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

    google_oauth_client_id: str = Field(
        default="",
        description=(
            "Google OAuth Web client ID (GOOGLE_OAUTH_CLIENT_ID). Public — also the frontend's "
            "VITE_GOOGLE_CLIENT_ID. The audience the backend verifies Google ID tokens against."
        ),
    )
    google_oauth_client_secret: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Google OAuth client secret (GOOGLE_OAUTH_CLIENT_SECRET). Not needed to VERIFY ID "
            "tokens (the flow used here); stored for a possible future auth-code exchange."
        ),
    )
    allowed_emails: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description=(
            "Allowlist of Google emails permitted to sign in (ALLOWED_EMAILS, comma-separated). "
            "Enforced server-side after Google verification; a non-listed email gets 403 (ADR-018)."
        ),
    )
    jwt_secret: SecretStr = Field(
        default=SecretStr(""),
        description="Secret that signs app-session JWTs (JWT_SECRET). A long random string.",
    )
    auth_session_hours: int = Field(
        default=12,
        ge=1,
        description="App session (JWT + cookie) lifetime in hours.",
    )
    auth_cookie_secure: bool = Field(
        default=False,
        description=(
            "Set the session cookie's Secure flag (AUTH_COOKIE_SECURE). True in prod over HTTPS; "
            "False for localhost-http (a Secure cookie over http is dropped)."
        ),
    )

    @field_validator("allowed_emails", mode="before")
    @classmethod
    def _split_allowed_emails(cls, value: object) -> object:
        # ALLOWED_EMAILS is a comma-separated string in the env, not JSON; NoDecode hands it
        # here raw so we split + normalise (lowercased, stripped, blanks dropped).
        if isinstance(value, str):
            return [e.strip().lower() for e in value.split(",") if e.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings``. Cheap to call from anywhere."""
    return Settings()
