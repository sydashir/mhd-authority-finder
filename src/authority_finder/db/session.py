"""Async engine + session factory bound to ``Settings.database_url`` (ADR-013).

psycopg 3 (``postgresql+psycopg://``) drives both the async app (here) and sync Alembic.
``expire_on_commit=False`` is mandatory under asyncio — otherwise attribute access after a
commit triggers blocking IO and raises.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from authority_finder.config import get_settings


def make_engine(url: str | None = None) -> AsyncEngine:
    """Create an async engine for ``url`` (defaults to the configured ``DATABASE_URL``)."""
    return create_async_engine(url or get_settings().database_url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Async session factory (``expire_on_commit=False`` — required for async)."""
    return async_sessionmaker(engine, expire_on_commit=False)
