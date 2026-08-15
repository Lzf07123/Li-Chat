from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import Settings
from app.db import Base, build_engine, build_sessionmaker
from app.logging import configure_logging
from app.oidc.discovery import DiscoveryStore
from app.sso.routes import router as sso_router


def create_app(
    settings: Settings | None = None,
    *,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    app_settings = settings or Settings()
    configure_logging(app_settings.env)
    engine = build_engine(app_settings.database_url)
    session_factory = build_sessionmaker(engine)
    discovery = DiscoveryStore(
        app_settings.discovery_url,
        transport=http_transport,
        ttl=app_settings.discovery_cache_ttl,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.discovery = discovery
    app.state.http_transport = http_transport

    app.include_router(sso_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
