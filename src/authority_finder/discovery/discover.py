"""Discovery orchestrator: queries → search → parse → classify → dedupe.

``discover_for_geo`` runs one geo's pipeline; per-query failures are recorded
as :class:`DiscoveryError` data, not raised — one dead query must not void the
other queries' results. ``discover_many`` adds semaphore-capped concurrency
(SerpAPI enforces hourly throughput caps) with per-geo isolation: a geo that
fails outright comes back as an empty result carrying the error, so the return
type stays uniform for callers.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from pydantic import ValidationError

from authority_finder.discovery.classify import dedupe_candidates
from authority_finder.discovery.models import (
    DiscoveryError,
    DiscoveryResult,
    GeoRef,
    SearchResult,
)
from authority_finder.discovery.queries import build_queries
from authority_finder.discovery.serpapi_client import (
    QuotaExceededError,
    SerpApiClient,
    SerpApiError,
)
from authority_finder.geo_monitor.models import GeoPage

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def parse_organic_results(data: dict[str, Any], *, query: str) -> list[SearchResult]:
    """Convert one raw SerpAPI payload into typed results, skipping malformed rows."""
    out: list[SearchResult] = []
    for raw in data.get("organic_results", []):
        try:
            result = SearchResult(
                position=raw["position"],
                title=raw["title"],
                link=raw["link"],
                snippet=raw.get("snippet", ""),
                source_query=query,
            )
        except (KeyError, TypeError, ValidationError) as exc:
            _log.warning("discovery.result_skipped", query=query, error=str(exc))
            continue
        out.append(result)
    return out


async def discover_for_geo(geo: GeoPage, *, client: SerpApiClient) -> DiscoveryResult:
    """Run discovery for one geo: all level queries, sequentially, cache-aware."""
    started = datetime.now(UTC)
    ref = GeoRef.from_geo_page(geo)
    queries = build_queries(geo)
    _log.info("discovery.start", geo=geo.url, level=geo.level, queries=len(queries))

    results: list[SearchResult] = []
    errors: list[DiscoveryError] = []
    billed = 0
    for query in queries:
        try:
            raw = await client.search(query)
        except (SerpApiError, httpx.HTTPError) as exc:
            _log.warning("discovery.query_failed", geo=geo.url, query=query, error=str(exc))
            errors.append(DiscoveryError(query=query, message=str(exc)))
            continue
        billed += int(raw.billed)
        results.extend(parse_organic_results(raw.data, query=query))

    candidates, counts = dedupe_candidates(results, geo=ref, now=started)
    _log.info(
        "discovery.finish",
        geo=geo.url,
        candidates=len(candidates),
        counts_by_class=dict(counts),
        billed_searches=billed,
        errors=len(errors),
    )
    return DiscoveryResult(
        geo=ref,
        candidates=candidates,
        counts_by_class=counts,
        queries_run=len(queries),
        billed_searches=billed,
        errors=errors,
    )


async def discover_many(
    geos: list[GeoPage], *, client: SerpApiClient, concurrency: int = 2
) -> list[DiscoveryResult]:
    """Run discovery across geos with bounded concurrency and per-geo isolation."""
    sem = asyncio.Semaphore(concurrency)

    async def run_one(geo: GeoPage) -> DiscoveryResult:
        async with sem:
            return await discover_for_geo(geo, client=client)

    raw_results = await asyncio.gather(*(run_one(g) for g in geos), return_exceptions=True)

    out: list[DiscoveryResult] = []
    for geo, result in zip(geos, raw_results, strict=True):
        if isinstance(result, QuotaExceededError):
            # Cost circuit breaker — abort the whole run, don't mask it as a per-geo error.
            raise result
        if isinstance(result, BaseException):
            _log.error("discovery.geo_failed", geo=geo.url, error=str(result))
            out.append(
                DiscoveryResult(
                    geo=GeoRef.from_geo_page(geo),
                    queries_run=0,
                    billed_searches=0,
                    errors=[DiscoveryError(query="", message=str(result))],
                )
            )
        else:
            out.append(result)
    return out
