"""Request-scoped dependencies (ADR-014).

The DB session is reached through ``request.app.state.sessionmaker`` (built in the
app lifespan), never a module-level engine — so the engine lifecycle is bound to
the app instance and tests can run their own DB by overriding :func:`get_session`.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from authority_finder.config import Settings


def get_app_settings(request: Request) -> Settings:
    """The app's resolved Settings (set on app.state by the lifespan / create_app)."""
    settings: Settings = request.app.state.settings
    return settings


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    """The app-level session factory itself — for code that opens its OWN session
    outside the request scope (the background run task, whose request session is
    already closed by the time it runs)."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    return factory


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield a session from the app-level factory; it rolls back on error and always closes.

    Routers/repository must commit explicitly — the context manager does not auto-commit.
    """
    async with get_sessionmaker(request)() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SessionmakerDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
