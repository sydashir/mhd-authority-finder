"""Backend error monitoring (ADR-023) — the FastAPI-flavoured wrapper over the shared core.

Adds the Starlette + FastAPI integrations (request context, transaction names) to the shared
``init_sentry``. No-op unless ``SENTRY_DSN`` is set, so local dev + tests are silent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from authority_finder.monitoring import init_sentry

if TYPE_CHECKING:
    from authority_finder.config import Settings


def init_monitoring(settings: Settings) -> bool:
    """Initialise Sentry for the API iff a DSN is configured. Returns whether it was enabled."""
    return init_sentry(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )
