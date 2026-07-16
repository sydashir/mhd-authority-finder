"""Shared Sentry init + scrubbing core (ADR-023).

No web-framework dependency — the backend adds the FastAPI integration on top, the standalone
scheduler uses it bare. Enabled ONLY when a DSN is given, so local dev is silent: with no DSN,
``init_sentry`` never runs and every ``sentry_sdk.capture_*`` call is a no-op. Scrubbing is
layered: ``send_default_pii=False`` (the default) denies authorization/cookie/session/token/
secret/api_key from event payloads + request headers; ``scrub_event`` additionally drops the
request cookies + body outright and redacts email addresses (prospect PII) from messages.
"""

from __future__ import annotations

import re
from typing import Any, cast

import sentry_sdk

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SENSITIVE_HEADERS = {"cookie", "authorization", "x-api-key", "proxy-authorization"}


def _redact(text: str) -> str:
    return _EMAIL_RE.sub("[email]", text)


def scrub_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """before_send hook: strip the request cookies/body/sensitive headers and redact emails.

    Sentry's Event is loosely typed (``dict[str, Any]``), so nested pieces are cast to concrete
    shapes as they are narrowed — keeps the intent explicit and the type checker satisfied.
    """
    request = event.get("request")
    if isinstance(request, dict):
        req = cast("dict[str, Any]", request)
        req.pop("cookies", None)
        req.pop("data", None)  # never ship request bodies
        headers = req.get("headers")
        if isinstance(headers, dict):
            hdr = cast("dict[str, Any]", headers)
            for key in [k for k in hdr if str(k).lower() in _SENSITIVE_HEADERS]:
                hdr[key] = "[scrubbed]"
    exception = event.get("exception")
    if isinstance(exception, dict):
        values = cast("dict[str, Any]", exception).get("values")
        if isinstance(values, list):
            for value in cast("list[Any]", values):
                if isinstance(value, dict):
                    entry = cast("dict[str, Any]", value)
                    text = entry.get("value")
                    if isinstance(text, str):
                        entry["value"] = _redact(text)
    message = event.get("message")
    if isinstance(message, str):
        event["message"] = _redact(message)
    return event


def init_sentry(*, dsn: str, environment: str, integrations: list[Any] | None = None) -> bool:
    """Initialise Sentry iff a DSN is given. Returns whether monitoring was enabled."""
    if not dsn:
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=integrations or [],
        send_default_pii=False,  # auto-denies auth/cookie/session/token/secret/api_key
        before_send=scrub_event,  # type: ignore[arg-type]  (Sentry's Event ≈ dict[str, Any])
        traces_sample_rate=0.0,  # errors only — free-tier friendly, no perf spans
    )
    return True
