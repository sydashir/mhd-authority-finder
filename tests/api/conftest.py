"""Backend API test harness: drive the app in-process with httpx ASGITransport
and inject the testcontainer-backed AsyncSession via dependency override.

ASGITransport does NOT run the app's lifespan, so ``app.state.sessionmaker`` is
never built and no real DATABASE_URL engine is created — endpoints read the test
DB purely through the overridden ``get_session`` (ADR-014).
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.config import Settings
from backend.app import create_app, get_session


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    app = create_app(Settings(cors_allow_origins=["http://localhost:5173"]))

    async def _override_get_session() -> AsyncGenerator[AsyncSession]:
        yield session  # the testcontainer session the test seeds + commits

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)  # httpx 0.28: app= shortcut removed
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()  # app is per-test, but be explicit
