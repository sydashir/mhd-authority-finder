"""Request-scoped dependencies (ADR-014).

The DB session is reached through ``request.app.state.sessionmaker`` (built in the
app lifespan), never a module-level engine — so the engine lifecycle is bound to
the app instance and tests can run their own DB by overriding :func:`get_session`.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield a session from the app-level factory; it rolls back on error and always closes.

    Routers/repository must commit explicitly — the context manager does not auto-commit.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
