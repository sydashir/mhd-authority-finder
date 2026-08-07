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
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Anthropic API key for per-domain link classification (ADR-040). "
            "Absent = the learning layer is simply skipped; seeds still work."
        ),
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
            "a workbook it can edit. Defaults to GOOGLE_SHEET_ID; the auto-write tab is never "
            "touched. Point this at a dedicated workbook to keep exports out of the client's file."
        ),
    )

    ahrefs_dr_threshold: int = Field(
        default=25,
        ge=0,
        le=100,
        description=(
            "Minimum Domain Rating for a non-.gov/.edu site to be retained. DEVIATES from "
            "the brief's 'e.g. DR 40+' on calibration evidence (ADR-026): the brief's own "
            "named example ncala.org scores 34, txcouncil.com 32 and calbhbc.org 29, so 40 "
            "rejects exactly the state-level orgs component 3 exists to find. Provisional "
            "pending client ratification."
        ),
    )

    run_interval_hours: int = Field(
        default=24,
        ge=1,
        description=(
            "DEPRECATED: superseded by RUN_DAYS/RUN_TIME cron scheduling. Retained so an "
            "existing .env keeps loading; no longer drives the scheduler."
        ),
    )

    run_days: str = Field(
        default="mon,wed",
        description="Days the scheduler runs, comma-separated (RUN_DAYS), e.g. 'mon,wed'.",
    )

    run_time: str = Field(
        default="03:00",
        description="Local time of day the scheduler runs, HH:MM 24h (RUN_TIME).",
    )

    run_timezone: str = Field(
        default="America/New_York",
        description=(
            "IANA timezone the schedule is interpreted in (RUN_TIMEZONE). Defaults to US "
            "Eastern, NOT the server's UTC: the client is US-based and a 03:00 run is meant "
            "to land before their business day. Under UTC the run would drift across their "
            "working hours twice a year as US daylight saving shifts."
        ),
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

    auth_users: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description=(
            "Sign-in credentials (AUTH_USERS, comma-separated ``username:hash`` pairs, ADR-026). "
            "The hash is scrypt — mint one with `python -m authority_finder.cli create-user`. "
            "Plaintext passwords are never stored. Empty = nobody can sign in."
        ),
    )
    auth_max_failed_logins: int = Field(
        default=8,
        ge=1,
        description=(
            "Failed sign-ins from one client before it is temporarily locked out "
            "(AUTH_MAX_FAILED_LOGINS) — brute-force protection for password auth."
        ),
    )
    auth_lockout_minutes: int = Field(
        default=15,
        ge=1,
        description="How long a locked-out client must wait (AUTH_LOCKOUT_MINUTES).",
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

    @field_validator("auth_users", mode="before")
    @classmethod
    def _split_auth_users(cls, value: object) -> object:
        # AUTH_USERS is a comma-separated string in the env, not JSON; NoDecode hands it here
        # raw. Only commas separate entries — the scrypt hash itself contains '$' and base64.
        if isinstance(value, str):
            return [entry.strip() for entry in value.split(",") if entry.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings``. Cheap to call from anywhere."""
    return Settings()
