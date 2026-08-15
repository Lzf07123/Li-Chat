import asyncio
from contextlib import suppress
from typing import cast

import httpx
from fakeredis.aioredis import FakeRedis

from app.auth.session import create_session
from app.config import Settings
from app.db import Base
from app.main import create_app
from app.models import User
from app.redis import logout_subscriber
from app.ws.manager import ConnectionManager
from tests.fixtures.mock_idp import MockIdP

_EVENT = "http://schemas.openid.net/event/backchannel-logout"


class FakeWS:
    def __init__(self) -> None:
        self.closed_with: list[int] = []

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed_with.append(code)

    async def send_json(self, data, mode: str = "text") -> None:
        pass


def _settings(tmp_path, mock_idp: MockIdP) -> Settings:
    return Settings(
        _env_file=None,
        env="dev",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'shared.db'}",
        oidc_issuer=mock_idp.ISSUER,
        oidc_discovery_url=f"{mock_idp.ISSUER}/.well-known/openid-configuration",
        oidc_client_id=mock_idp.client_id,
        oidc_client_secret=mock_idp.client_secret,
        oidc_redirect_uri="http://test/oidc/callback",
        oidc_post_logout_redirect_uri="http://test/",
        session_secret="test-session-secret",
    )


async def _logout_token(mock_idp: MockIdP, jti: str) -> str:
    return mock_idp.sign_logout_token(
        {
            "sub": "u-1",
            "sid": "sid-1",
            "jti": jti,
            "events": {_EVENT: {}},
        }
    )


async def test_backchannel_logout_reaches_other_replica(
    tmp_path, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> None:
    redis = FakeRedis(decode_responses=True)
    settings = _settings(tmp_path, mock_idp)
    app_a = create_app(settings, http_transport=mock_transport, redis=redis)
    app_b = create_app(settings, http_transport=mock_transport, redis=redis)
    async with app_a.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with app_a.state.session_factory() as db:
        db.add(User(sub="u-1", nickname="A"))
        await create_session(db, "u-1", sid="sid-1")
    fake = FakeWS()
    await app_b.state.ws_manager.connect("u-1", fake)
    subscriber = asyncio.create_task(
        logout_subscriber(redis, cast(ConnectionManager, app_b.state.ws_manager))
    )

    transport_a = httpx.ASGITransport(app=app_a)
    async with httpx.AsyncClient(
        transport=transport_a, base_url="http://test", follow_redirects=False
    ) as client:
        first = await client.post(
            "/oidc/backchannel-logout",
            data={"logout_token": await _logout_token(mock_idp, "j-cross-1")},
        )
        assert first.status_code == 200
        await asyncio.sleep(0.1)
        assert fake.closed_with == [4401]

        second = await client.post(
            "/oidc/backchannel-logout",
            data={"logout_token": await _logout_token(mock_idp, "j-cross-1")},
        )
        assert second.status_code == 200
        assert second.json()["status"] == "ignored"

    subscriber.cancel()
    with suppress(asyncio.CancelledError):
        await subscriber
    await app_a.state.engine.dispose()
    await app_b.state.engine.dispose()
    await redis.aclose()
