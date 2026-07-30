"""Async Ahrefs API v3 client for Domain Rating lookups, with a disk response cache.

Batch-first by necessity, not preference. Ahrefs bills
``units = max(base_cost=50, per_row_cost * rows)``, and ``/site-explorer/domain-rating``
accepts no ``select``/``where``, so it always floors at the 50-unit base cost — for ONE
domain. ``/batch-analysis/batch-analysis`` takes up to 100 targets and measured 60 units
for 20 domains (3 units each), so batching is roughly 17x cheaper per domain. We never
loop the single-domain endpoint.

Shape notes, all confirmed against the live API (the published docs are wrong in two
places): the single endpoint nests its payload one level deep, ``domain_rating`` is a
float rather than an integer, each ``targets`` entry REQUIRES a ``protocol`` field (a 400
otherwise), and returned URLs carry a trailing slash that must be stripped before keying
results back to the requested domain.

The cache (``data/cache/ahrefs/{sha256}.json``, no TTL — dev-phase, ADR-005) is keyed on
the domain alone and never contains a trace of the key, so re-runs cost zero units.
Spend is read from the ``x-api-units-cost-total`` response header rather than estimated.
"""

import asyncio
import hashlib
import json
from collections.abc import Sequence
from http import HTTPStatus
from pathlib import Path
from types import TracebackType
from typing import Any, NamedTuple, Self, cast

import httpx
import structlog
from pydantic import SecretStr
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

BATCH_URL = "https://api.ahrefs.com/v3/batch-analysis/batch-analysis"
USAGE_URL = "https://api.ahrefs.com/v3/subscription-info/limits-and-usage"
BATCH_LIMIT = 100
DEFAULT_CACHE_DIR = Path("data/cache/ahrefs")
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
_SELECT = ["url", "domain_rating", "ahrefs_rank"]

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AhrefsError(RuntimeError):
    """Non-retryable Ahrefs failure (auth, bad request, malformed response)."""


class AhrefsQuotaExceededError(RuntimeError):
    """The per-run Ahrefs call cap was reached — a cost circuit breaker.

    Deliberately not an :class:`AhrefsError`, so a per-domain handler cannot swallow it.
    """


class RetryableAhrefsError(AhrefsError):
    """429 or 5xx — retried, honoring Retry-After when present."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class DomainRating(NamedTuple):
    """One domain's authority. ``dr`` is None when Ahrefs has no data for it.

    None and 0.0 are different answers and must not be conflated: 0.0 is a real domain
    with no link profile (a parked or dead site), None is an absence of information.
    """

    domain: str
    dr: float | None
    ahrefs_rank: int | None


def _normalise(target: str) -> str:
    """``https://Ncala.org/path/`` -> ``ncala.org``."""
    cleaned = target.strip().lower()
    for prefix in ("https://", "http://"):
        cleaned = cleaned.removeprefix(prefix)
    return cleaned.split("/", 1)[0].removeprefix("www.")


class AhrefsClient:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        max_calls: int | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._key = api_key
        self._cache_dir = cache_dir
        self._max_calls = max_calls
        self._client = http_client
        self._owns_client = http_client is None
        self.call_count = 0
        self.cache_hit_count = 0
        self.units_spent = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
            self._owns_client = True
        return self._client

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key.get_secret_value()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def domain_ratings(self, domains: Sequence[str]) -> dict[str, DomainRating]:
        """Look up DR for ``domains``, serving from the disk cache where possible."""
        wanted = list(dict.fromkeys(_normalise(d) for d in domains if d.strip()))
        if not wanted:
            return {}

        ratings: dict[str, DomainRating] = {}
        missing: list[str] = []
        for domain in wanted:
            cached = self._cache_read(domain)
            if cached is None:
                missing.append(domain)
                continue
            self.cache_hit_count += 1
            ratings[domain] = DomainRating(
                domain=domain, dr=cached.get("domain_rating"), ahrefs_rank=cached.get("ahrefs_rank")
            )

        for start in range(0, len(missing), BATCH_LIMIT):
            chunk = missing[start : start + BATCH_LIMIT]
            for scored in await self._fetch_batch(chunk):
                ratings[scored.domain] = scored
            # A domain the API returned nothing for is still resolved, as an absence.
            for domain in chunk:
                ratings.setdefault(domain, DomainRating(domain=domain, dr=None, ahrefs_rank=None))
        return ratings

    async def _fetch_batch(self, chunk: list[str]) -> list[DomainRating]:
        if self._max_calls is not None and self.call_count >= self._max_calls:
            raise AhrefsQuotaExceededError(f"Ahrefs call cap reached ({self._max_calls})")

        body = {
            "select": _SELECT,
            "targets": [{"url": d, "mode": "domain", "protocol": "both"} for d in chunk],
        }
        response = await self._request(body)
        self.call_count += 1
        self.units_spent += int(response.headers.get("x-api-units-cost-total") or 0)

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise AhrefsError("Ahrefs returned a non-JSON body") from exc

        entries = cast("list[dict[str, Any]]", payload.get("targets") or [])
        out: list[DomainRating] = []
        for entry in entries:
            domain = _normalise(str(entry.get("url") or ""))
            if not domain:
                continue
            dr = entry.get("domain_rating")
            rank = entry.get("ahrefs_rank")
            out.append(
                DomainRating(
                    domain=domain,
                    dr=None if dr is None else float(dr),
                    ahrefs_rank=None if rank is None else int(rank),
                )
            )
            self._cache_write(domain, {"domain_rating": dr, "ahrefs_rank": rank})
        _log.info("ahrefs.batch", requested=len(chunk), returned=len(out))
        return out

    async def _request(self, body: dict[str, Any]) -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_fixed(2),
            retry=retry_if_exception_type(RetryableAhrefsError),
            reraise=True,
        ):
            with attempt:
                response = await self._http.post(BATCH_URL, json=body, headers=self._headers)
                if (
                    response.status_code == HTTPStatus.TOO_MANY_REQUESTS
                    or response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
                ):
                    retry_after = response.headers.get("retry-after")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else None
                    if delay:
                        await asyncio.sleep(min(delay, 30.0))
                    raise RetryableAhrefsError(f"Ahrefs {response.status_code}", retry_after=delay)
                if response.status_code != HTTPStatus.OK:
                    # Body may name the offending field; it never contains the key.
                    raise AhrefsError(f"Ahrefs {response.status_code}: {response.text[:200]}")
                return response
        raise AhrefsError("Ahrefs retries exhausted")

    async def limits_and_usage(self) -> dict[str, Any]:
        """Workspace unit budget. Appears free, and is the truth when free targets are used
        (the per-response header over-reports for ahrefs.com / wordcount.com)."""
        response = await self._http.get(USAGE_URL, headers=self._headers)
        if response.status_code != HTTPStatus.OK:
            raise AhrefsError(f"Ahrefs usage {response.status_code}")
        payload: dict[str, Any] = response.json()
        return payload.get("limits_and_usage") or payload

    def _cache_path(self, domain: str) -> Path:
        digest = hashlib.sha256(domain.encode()).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def _cache_read(self, domain: str) -> dict[str, Any] | None:
        path = self._cache_path(domain)
        if not path.is_file():
            return None
        try:
            loaded: dict[str, Any] = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        return loaded

    def _cache_write(self, domain: str, data: dict[str, Any]) -> None:
        path = self._cache_path(domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True))
        tmp.replace(path)
