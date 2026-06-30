"""FastAPI application factory (ADR-014).

A factory (not a bare module-global) so tests build an isolated app and prod gets
``backend.app:app``. The async engine + sessionmaker live on ``app.state`` via the
lifespan and are disposed on shutdown; CORS origins come from typed settings.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from authority_finder.config import Settings, get_settings
from authority_finder.db.session import make_engine, make_session_factory
from backend.deps import get_session
from backend.jobs import sweep_orphan_runs
from backend.routers import health, prospects, runs, stats

__all__ = ["app", "create_app", "get_session"]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        engine = make_engine(settings.database_url)
        app.state.engine = engine
        app.state.sessionmaker = make_session_factory(engine)
        # A prior crash can't leave a ghost 'running' row in the history.
        await sweep_orphan_runs(app.state.sessionmaker)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="MHD Authority Finder API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(stats.router)
    app.include_router(prospects.router)
    app.include_router(runs.router)
    return app


app = create_app()
