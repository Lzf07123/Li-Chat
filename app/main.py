from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.api.friends import router as friends_router
from app.api.messages import router as messages_router
from app.api.users import router as users_router
from app.auth.session import get_session
from app.config import Settings
from app.db import Base, build_engine, build_sessionmaker
from app.logging import configure_logging, get_logger
from app.oidc.discovery import DiscoveryStore
from app.redis import build_redis, logout_subscriber
from app.sso.replay import MemoryReplayCache, RedisReplayCache, ReplayCache
from app.sso.routes import router as sso_router
from app.ws.manager import ConnectionManager

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger = get_logger(__name__)


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url[len(prefix) :]
    if raw == ":memory:" or raw.startswith("file:"):
        return None
    path = Path(raw)
    return path if path.is_absolute() else Path.cwd() / path


def create_app(
    settings: Settings | None = None,
    *,
    http_transport: httpx.AsyncBaseTransport | None = None,
    redis: Redis | None = None,
) -> FastAPI:
    app_settings = settings or Settings()
    configure_logging(app_settings.env)
    engine = build_engine(app_settings.database_url)
    session_factory = build_sessionmaker(engine)
    redis_client = redis if redis is not None else build_redis(app_settings.redis_url)
    replay_cache: ReplayCache
    if redis_client is not None:
        replay_cache = RedisReplayCache(
            redis_client, ttl=app_settings.logout_token_max_skew + 60
        )
    else:
        replay_cache = MemoryReplayCache(
            ttl=app_settings.logout_token_max_skew + 60
        )
    discovery = DiscoveryStore(
        app_settings.discovery_url,
        transport=http_transport,
        ttl=app_settings.discovery_cache_ttl,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database_path = _sqlite_path(app_settings.database_url)
        if database_path is not None:
            database_path.parent.mkdir(parents=True, exist_ok=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        subscriber: asyncio.Task[None] | None = None
        if redis_client is not None:
            await redis_client.ping()
            manager = cast(ConnectionManager, app.state.ws_manager)
            subscriber = asyncio.create_task(logout_subscriber(redis_client, manager))
            logger.info("redis_connected", url=app_settings.redis_url)
        yield
        if subscriber is not None:
            subscriber.cancel()
            with suppress(asyncio.CancelledError):
                await subscriber
        await engine.dispose()
        if redis_client is not None:
            await redis_client.aclose()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.discovery = discovery
    app.state.http_transport = http_transport
    app.state.redis = redis_client
    app.state.ws_manager = ConnectionManager()
    app.state.replay_cache = replay_cache

    app.include_router(sso_router)
    app.include_router(users_router)
    app.include_router(friends_router)
    app.include_router(messages_router)

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

    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app


app = create_app()
