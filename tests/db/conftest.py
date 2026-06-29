"""Real-Postgres test fixtures (ADR-013) — testcontainers, not mocks.

A persistence layer is only proven against a real database, so these spin an
ephemeral Postgres via testcontainers (one container per session) and give each
test a clean schema. Skipped cleanly when Docker is unavailable.
"""

from collections.abc import AsyncGenerator, Iterator

import docker
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from authority_finder.db.models import Base


def _docker_available() -> bool:
    try:
        docker.from_env().ping()  # pyright: ignore[reportUnknownMemberType]  (docker SDK untyped)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available — real-Postgres repository tests need it")
    with PostgresContainer("postgres:16") as pg:
        # get_connection_url() returns a psycopg2 URL; drive it async with psycopg 3.
        yield pg.get_connection_url().replace("+psycopg2", "+psycopg")


@pytest_asyncio.fixture
async def session(pg_url: str) -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db_session:
            yield db_session
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
