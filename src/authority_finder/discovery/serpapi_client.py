"""Async SerpAPI client with a disk response cache.

Engine is ``google_light`` (ADR-005): ``google_light_fast`` was retired by
SerpAPI, and no Google engine accepts ``num`` anymore — one billed search
returns one ~10-result page. We take page 1 only; depth is the ``start``
kwarg if we ever need it.

The cache (``data/cache/serpapi/{sha256}.json``, no TTL — dev-phase, ADR-005)
exists to make iteration free: a cache hit is zero billed searches. The key
hashes the full param set minus ``api_key``, so cached files never depend on
(or contain a trace of) the secret.
"""

import hashlib
import json
from http import HTTPStatus
from pathlib import Path
from typing import Any, NamedTuple

import httpx
import structlog
from pydantic import SecretStr
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
)

ENGINE = "google_light"
SEARCH_URL = "https://serpapi.com/search.json"
DEFAULT_CACHE_DIR = Path("data/cache/serpapi")
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SerpApiError(RuntimeError):
    """Non-retryable SerpAPI failure (bad request, auth, malformed response)."""


class RetryableSerpApiError(SerpApiError):
    """429 or 5xx — retried with backoff, honoring Retry-After when present."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RawSearch(NamedTuple):
    """One search response plus whether it cost a billed SerpAPI search."""

    data: dict[str, Any]
    billed: bool


class SerpApiClient:
    """Cache-aware SerpAPI search client. Counts billed searches for quota reporting."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        api_key: SecretStr,
        cache_dir: Path = DEFAULT_CACHE_DIR,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._cache_dir = cache_dir
        self.billed_search_count = 0
        self.cache_hit_count = 0

    async def search(
        self, query: str, *, gl: str = "us", hl: str = "en", start: int = 0
    ) -> RawSearch:
        """Run one Google Light search, serving from the disk cache when possible."""
        params: dict[str, str] = {"engine": ENGINE, "q": query, "gl": gl, "hl": hl}
        if start:
            params["start"] = str(start)

        cached = self._cache_read(params)
        if cached is not None:
            self.cache_hit_count += 1
            _log.debug("serpapi.cache_hit", query=query)
            return RawSearch(data=cached, billed=False)

        data = await self._fetch(params)
        self.billed_search_count += 1
        _log.info("serpapi.billed_search", query=query, session_total=self.billed_search_count)
        self._cache_write(params, data)
        return RawSearch(data=data, billed=True)

    async def _fetch(self, params: dict[str, str]) -> dict[str, Any]:
        full_params = {**params, "api_key": self._api_key.get_secret_value()}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=_retry_wait,
            retry=retry_if_exception_type((httpx.TransportError, RetryableSerpApiError)),
            reraise=True,
            before_sleep=_log_before_sleep,
        ):
            with attempt:
                resp = await self._client.get(
                    SEARCH_URL, params=full_params, timeout=DEFAULT_TIMEOUT
                )
                if (
                    resp.status_code == HTTPStatus.TOO_MANY_REQUESTS
                    or resp.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
                ):
                    raise RetryableSerpApiError(
                        f"serpapi returned {resp.status_code}",
                        retry_after=_parse_retry_after(resp.headers.get("Retry-After")),
                    )
                if resp.status_code != HTTPStatus.OK:
                    raise SerpApiError(f"serpapi {resp.status_code}: {resp.text[:200]}")
                data: dict[str, Any] = resp.json()
                if "error" in data:
                    raise SerpApiError(f"serpapi error: {data['error']}")
                return data
        raise RuntimeError("unreachable: AsyncRetrying yielded no attempts")

    def _cache_path(self, params: dict[str, str]) -> Path:
        digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def _cache_read(self, params: dict[str, str]) -> dict[str, Any] | None:
        path = self._cache_path(params)
        try:
            text = path.read_text()
        except FileNotFoundError:
            return None
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            # Corrupt entry (interrupted write): treat as a miss and overwrite.
            return None
        return data

    def _cache_write(self, params: dict[str, str], data: dict[str, Any]) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(params).write_text(json.dumps(data))


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _retry_wait(retry_state: RetryCallState) -> float:
    """Exponential backoff (2, 4, 8... capped at 30s); Retry-After wins when given."""
    exc = retry_state.outcome.exception() if retry_state.outcome is not None else None
    if isinstance(exc, RetryableSerpApiError) and exc.retry_after is not None:
        return min(exc.retry_after, 60.0)
    return min(2.0**retry_state.attempt_number, 30.0)


def _log_before_sleep(retry_state: RetryCallState) -> None:
    error = retry_state.outcome.exception() if retry_state.outcome is not None else None
    _log.warning(
        "serpapi.retry",
        attempt=retry_state.attempt_number,
        error=str(error) if error else None,
    )
