from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import Base
from app.main import create_app
from tests.fixtures.mock_idp import MockIdP


@pytest.fixture
def mock_idp() -> MockIdP:
    return MockIdP()


@pytest.fixture
def mock_transport(mock_idp: MockIdP) -> httpx.ASGITransport:
    return httpx.ASGITransport(app=mock_idp.app)


@pytest.fixture
def settings(tmp_path, mock_idp: MockIdP) -> Settings:
    return Settings(
        _env_file=None,
        env="dev",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        oidc_issuer=mock_idp.ISSUER,
        oidc_discovery_url=f"{mock_idp.ISSUER}/.well-known/openid-configuration",
        oidc_client_id=mock_idp.client_id,
        oidc_client_secret=mock_idp.client_secret,
        oidc_redirect_uri="http://localhost:8000/oidc/callback",
        oidc_post_logout_redirect_uri="http://localhost:8000/",
        session_secret="test-session-secret",
    )


@pytest.fixture
async def app(settings: Settings, mock_transport: httpx.ASGITransport):
    application = create_app(settings, http_transport=mock_transport)
    async with application.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield application
    async with application.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await application.state.engine.dispose()


@pytest.fixture
async def api_client(app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as client:
        yield client


@pytest.fixture
async def mock_client(mock_transport: httpx.ASGITransport) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=mock_transport, follow_redirects=False) as client:
        yield client


@pytest.fixture
async def db_session(app) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:
        yield session
