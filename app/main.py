from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import cast

import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.api.friends import router as friends_router
from app.api.groups import router as groups_router
from app.api.messages import router as messages_router
from app.api.search import router as search_router
from app.api.uploads import router as uploads_router
from app.api.users import router as users_router
from app.auth.session import get_session
from app.config import Settings
from app.db import Base, build_engine, build_sessionmaker
from app.friends.service import list_friends
from app.logging import configure_logging, get_logger
from app.models import User
from app.oidc.discovery import DiscoveryStore
from app.redis import build_redis, logout_subscriber
from app.sso.replay import MemoryReplayCache, RedisReplayCache, ReplayCache
from app.sso.routes import router as sso_router
from app.timeutil import iso_utc, utcnow
from app.uploads.service import resolve_upload_root
from app.ws.calls import CallManager, handle_call
from app.ws.manager import ConnectionManager
from app.ws.relay import relay_typing

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger = get_logger(__name__)

_STATIC_PATHS = {
    "/",
    "/app.js",
    "/style.css",
    "/brand.js",
    "/theme.js",
    "/ambient.js",
    "/favicon.svg",
}


def _ensure_session_columns(conn: Connection) -> None:
    """SQLite 兼容迁移：为既有库补齐 sessions.id_token（PostgreSQL 走 Alembic）。"""
    if conn.dialect.name != "sqlite":
        return
    names = {
        row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)").fetchall()
    }
    if "id_token" not in names:
        conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN id_token TEXT")


def _ensure_user_columns(conn: Connection) -> None:
    """SQLite 兼容迁移：为既有库补齐 users.last_seen_at（PostgreSQL 走 Alembic）。"""
    if conn.dialect.name != "sqlite":
        return
    names = {
        row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
    }
    if "last_seen_at" not in names:
        conn.exec_driver_sql("ALTER TABLE users ADD COLUMN last_seen_at DATETIME")
    if "bio" not in names:
        conn.exec_driver_sql("ALTER TABLE users ADD COLUMN bio VARCHAR(200)")


def _ensure_message_columns(conn: Connection) -> None:
    """SQLite 兼容迁移：为既有库补齐 messages.edited_at/deleted_at。"""
    if conn.dialect.name != "sqlite":
        return
    names = {
        row[1] for row in conn.exec_driver_sql("PRAGMA table_info(messages)").fetchall()
    }
    if "edited_at" not in names:
        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN edited_at DATETIME")
    if "deleted_at" not in names:
        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN deleted_at DATETIME")
    if "conversation_type" not in names:
        conn.exec_driver_sql(
            "ALTER TABLE messages ADD COLUMN conversation_type VARCHAR(8) "
            "NOT NULL DEFAULT 'dm'"
        )
    if "group_id" not in names:
        conn.exec_driver_sql(
            "ALTER TABLE messages ADD COLUMN group_id INTEGER "
            "REFERENCES groups(id) ON DELETE CASCADE"
        )
    if "content_type" not in names:
        conn.exec_driver_sql(
            "ALTER TABLE messages ADD COLUMN content_type VARCHAR(16) "
            "NOT NULL DEFAULT 'text'"
        )
    if "attachment_name" not in names:
        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN attachment_name VARCHAR(255)")
    if "attachment_size" not in names:
        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN attachment_size INTEGER")
    if "attachment_mime" not in names:
        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN attachment_mime VARCHAR(64)")
    if "attachment_url" not in names:
        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN attachment_url VARCHAR(255)")
    if "reply_to_id" not in names:
        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN reply_to_id INTEGER")


async def _friend_subs(db: AsyncSession, sub: str) -> list[str]:
    friends = await list_friends(db, sub)
    return [friend["sub"] for friend in friends if friend["sub"] is not None]


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
        resolve_upload_root(app_settings).mkdir(parents=True, exist_ok=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_ensure_session_columns)
            await conn.run_sync(_ensure_user_columns)
            await conn.run_sync(_ensure_message_columns)
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

    @app.middleware("http")
    async def no_store_api(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def no_cache_static(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path in _STATIC_PATHS:
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.discovery = discovery
    app.state.http_transport = http_transport
    app.state.redis = redis_client
    app.state.ws_manager = ConnectionManager()
    app.state.call_manager = CallManager()
    app.state.replay_cache = replay_cache

    app.include_router(sso_router)
    app.include_router(users_router)
    app.include_router(friends_router)
    app.include_router(groups_router)
    app.include_router(messages_router)
    app.include_router(uploads_router)
    app.include_router(search_router)

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
        call_manager = cast(CallManager, app.state.call_manager)
        await manager.connect(user_sub, websocket)
        presence_peers: list[str] = []
        try:
            await websocket.send_json({"type": "hello", "sub": user_sub})
            async with session_factory() as db:
                user = await db.get(User, user_sub)
                if user is not None:
                    user.last_seen_at = utcnow()
                    await db.commit()
                presence_peers = await _friend_subs(db, user_sub)
            for friend_sub in presence_peers:
                await manager.send_to(
                    friend_sub,
                    {"type": "presence", "sub": user_sub, "online": True},
                )
            while True:
                try:
                    message = await websocket.receive_json()
                except ValueError:
                    continue
                if message.get("type") == "ping":
                    async with session_factory() as db:
                        valid = await get_session(
                            db, session_id, sliding_ttl=app_settings.session_sliding_ttl
                        )
                    if valid is None:
                        await websocket.close(code=4401)
                        return
                    user = await db.get(User, user_sub)
                    if user is not None:
                        user.last_seen_at = utcnow()
                        await db.commit()
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "typing":
                    async with session_factory() as db:
                        await relay_typing(db, manager, user_sub, message)
                elif message.get("type") == "call":
                    async with session_factory() as db:
                        await handle_call(db, manager, call_manager, user_sub, message)
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(user_sub, websocket)
            if manager.count(user_sub) == 0:
                offline = {
                    "type": "presence",
                    "sub": user_sub,
                    "online": False,
                    "last_seen_at": iso_utc(utcnow()),
                }
                for friend_sub in presence_peers:
                    await manager.send_to(friend_sub, offline)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app


app = create_app()
