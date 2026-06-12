"""Shared robots.txt checker: one fetch + parse per host, cached.

Extracted from the geo_monitor sitemap fetcher so the page detector (and any
future crawler) applies identical politeness rules under one user agent.
A robots.txt that can't be fetched (4xx, network error) is treated as
permissive — the standard convention.
"""

from http import HTTPStatus
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog

from authority_finder import __version__

USER_AGENT = (
    f"mhd-authority-finder/{__version__} (+https://github.com/sydashir/mhd-authority-finder)"
)

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt forbids fetching a target URL."""


class RobotsChecker:
    """Per-host cached robots.txt gate."""

    def __init__(self, *, client: httpx.AsyncClient, timeout: httpx.Timeout) -> None:
        self._client = client
        self._timeout = timeout
        self._cache: dict[str, RobotFileParser] = {}

    async def ensure_allowed(self, url: str) -> None:
        """Raise :class:`RobotsDisallowedError` if robots.txt forbids ``url``."""
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._cache.get(host)
        if rp is None:
            rp = await self._fetch(host)
            self._cache[host] = rp
        if not rp.can_fetch(USER_AGENT, url):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")

    async def _fetch(self, host: str) -> RobotFileParser:
        rp = RobotFileParser()
        robots_url = f"{host}/robots.txt"
        try:
            resp = await self._client.get(
                robots_url, headers={"User-Agent": USER_AGENT}, timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            _log.warning("robots.fetch_failed", host=host, error=str(exc))
            rp.parse([])
            return rp
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            rp.parse([])
            return rp
        rp.parse(resp.text.splitlines())
        return rp
