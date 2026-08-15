from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import httpx
from fastapi import FastAPI
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.api.users import router as users_router
from app.auth.session import get_session
from app.config import Settings
from app.db import Base, build_engine, build_sessionmaker
from app.logging import configure_logging
from app.oidc.discovery import DiscoveryStore
from app.sso.replay import ReplayCache
from app.sso.routes import router as sso_router
from app.ws.manager import ConnectionManager


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
    app.state.ws_manager = ConnectionManager()
    app.state.replay_cache = ReplayCache(ttl=app_settings.logout_token_max_skew + 60)

    app.include_router(sso_router)
    app.include_router(users_router)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        session_id = websocket.cookies.get(app_settings.session_cookie_name)
        await websocket.accept()
        if not session_id:
            await websocket.close(code=4401)
            return
        async with session_factory() as db:
            session = await get_session(
                db, session_id, sliding_ttl=app_settings.session_sliding_ttl
            )
            if session is None:
                await websocket.close(code=4401)
                return
            user_sub = session.user_sub
        manager = cast(ConnectionManager, app.state.ws_manager)
        await manager.connect(user_sub, websocket)
        try:
            await websocket.send_json({"type": "hello", "sub": user_sub})
            while True:
                try:
                    message = await websocket.receive_json()
                except ValueError:
                    continue
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(user_sub, websocket)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
