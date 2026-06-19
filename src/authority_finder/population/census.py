"""US Census ACS 5-year (2024) population lookup. Keyed (keyless retired 2026).

State → direct FIPS call. County/city → fetch every county/place in the state
once (wildcard, cached), then fuzzy-match the geo slug against the Census NAME
client-side (the wildcard rows carry the population too, so no second call).
Never fabricates: no key, no FIPS, no confident match, or a suppressed value
→ ``PopulationResult`` with ``not_found`` / ``value=None``.
"""

import difflib
import hashlib
import json
import re
import unicodedata
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import httpx
import structlog

from authority_finder.discovery.queries import county_display, slug_to_display
from authority_finder.geo_monitor.models import GeoPage
from authority_finder.population.fips import STATE_FIPS
from authority_finder.population.models import CensusLevel, MatchConfidence, PopulationResult

ACS5_BASE = "https://api.census.gov/data/2024/acs/acs5"
POP_VAR = "B01003_001E"
SOURCE_DATASET = "ACS 5-year 2024"
DEFAULT_CACHE_DIR = Path("data/cache/census")
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
_NO_DATA_FLOOR = -100_000_000  # ACS jam values: -666666666 etc. mean "no data"
_FUZZY_CUTOFF = 0.86
_MIN_ROWS = 2  # header + at least one data row

_TYPE_SUFFIXES = (
    " city",
    " town",
    " village",
    " borough",
    " cdp",
    " municipality",
    " metropolitan government",
    " county",
    " parish",
    " census area",
    " (balance)",
)

_ST_RE = re.compile(r"\bst\b")
_STE_RE = re.compile(r"\bste\b")

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def normalize_place(name: str) -> str:
    """Census NAME (or a geo display name) → comparable key: drop state tail + type suffix.

    Both ``St. Louis city`` (Census) and the slug-derived ``St Louis`` converge by
    dropping periods and expanding a standalone ``st``/``ste`` to ``saint``/``sainte``.
    """
    head = name.split(",", 1)[0]
    head = unicodedata.normalize("NFKD", head).encode("ascii", "ignore").decode()
    low = " ".join(head.casefold().split())
    for suffix in _TYPE_SUFFIXES:
        if low.endswith(suffix):
            low = low[: -len(suffix)].strip()
            break
    low = low.replace(".", "")
    low = _STE_RE.sub("sainte", low)
    low = _ST_RE.sub("saint", low)
    return " ".join(low.split())


def _parse_population(raw: str) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return None if value <= _NO_DATA_FLOOR or value < 0 else value


class CensusClient:
    """ACS5 population lookups with a disk cache. No key → every lookup is not_found."""

    def __init__(
        self, *, client: httpx.AsyncClient, api_key: str, cache_dir: Path = DEFAULT_CACHE_DIR
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._cache_dir = cache_dir

    async def population_for(self, geo: GeoPage) -> PopulationResult:
        if not self._api_key:
            return _not_found("no CENSUS_API_KEY configured")
        state_fips = STATE_FIPS.get(geo.state)
        if state_fips is None:
            return _not_found(f"no FIPS for state slug {geo.state!r}")

        if geo.level == "state":
            return await self._state(geo.state, state_fips)
        if geo.level == "county" and geo.county:
            return await self._match_in_state(
                target=county_display(geo.county),
                state_fips=state_fips,
                level="county",
                geo_unit="county",
            )
        if geo.level == "city" and geo.city:
            return await self._match_in_state(
                target=slug_to_display(geo.city),
                state_fips=state_fips,
                level="place",
                geo_unit="place",
            )
        return _not_found(f"unsupported geo level/slug: {geo.level}")

    async def _state(self, state_slug: str, state_fips: str) -> PopulationResult:
        rows = await self._get_rows(
            {"get": f"NAME,{POP_VAR}", "for": f"state:{state_fips}"}, f"state-{state_fips}"
        )
        if not rows or len(rows) < _MIN_ROWS:
            return _not_found(f"no ACS row for state {state_slug}")
        name, pop = rows[1][0], rows[1][1]
        return PopulationResult(
            value=_parse_population(pop),
            matched_name=name,
            geo_level_used="state",
            confidence="exact",
            source_dataset=SOURCE_DATASET,
        )

    async def _match_in_state(
        self, *, target: str, state_fips: str, level: CensusLevel, geo_unit: str
    ) -> PopulationResult:
        rows = await self._get_rows(
            {"get": f"NAME,{POP_VAR}", "for": f"{geo_unit}:*", "in": f"state:{state_fips}"},
            f"{geo_unit}-all-{state_fips}",
        )
        if not rows or len(rows) < _MIN_ROWS:
            return _not_found(f"no ACS {geo_unit} list for state {state_fips}")

        target_norm = normalize_place(target)
        candidates = {normalize_place(row[0]): row for row in rows[1:] if row and row[0]}

        match: list[str] | None = None
        confidence: MatchConfidence = "not_found"
        if target_norm in candidates:
            match, confidence = candidates[target_norm], "exact"
        else:
            close = difflib.get_close_matches(
                target_norm, list(candidates), n=1, cutoff=_FUZZY_CUTOFF
            )
            if close:
                match, confidence = candidates[close[0]], "fuzzy"

        if match is None:
            return _not_found(f"no {geo_unit} match for {target!r} in state {state_fips}")
        return PopulationResult(
            value=_parse_population(match[1]),
            matched_name=match[0],
            geo_level_used=level,
            confidence=confidence,
            source_dataset=SOURCE_DATASET,
            note="" if confidence == "exact" else f"fuzzy match of {target!r}",
        )

    async def _get_rows(self, params: dict[str, str], cache_name: str) -> list[list[str]] | None:
        cached = self._cache_read(cache_name)
        if cached is not None:
            return cached
        try:
            resp = await self._client.get(
                ACS5_BASE, params={**params, "key": self._api_key}, timeout=DEFAULT_TIMEOUT
            )
        except httpx.HTTPError as exc:
            _log.warning("census.fetch_failed", cache_name=cache_name, error=str(exc))
            return None
        if resp.status_code != HTTPStatus.OK:
            _log.warning("census.bad_status", cache_name=cache_name, status=resp.status_code)
            return None
        try:
            rows: list[list[str]] = resp.json()
        except json.JSONDecodeError:
            return None
        self._cache_write(cache_name, rows)
        return rows

    def _cache_path(self, cache_name: str) -> Path:
        digest = hashlib.sha256(cache_name.encode()).hexdigest()[:16]
        return self._cache_dir / f"{cache_name}-{digest}.json"

    def _cache_read(self, cache_name: str) -> list[list[str]] | None:
        try:
            data: Any = json.loads(self._cache_path(cache_name).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        return cast("list[list[str]]", data) if isinstance(data, list) else None

    def _cache_write(self, cache_name: str, rows: list[list[str]]) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(cache_name).write_text(json.dumps(rows))


def _not_found(note: str) -> PopulationResult:
    return PopulationResult(
        value=None,
        matched_name=None,
        geo_level_used=None,
        confidence="not_found",
        source_dataset=SOURCE_DATASET,
        note=note,
    )
