from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session
from app.timeutil import utcnow


async def _login(api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/oidc/login")
    authorize = await mock_client.get(response.headers["location"])
    callback = await api_client.get(authorize.headers["location"])
    assert callback.status_code == 302


async def test_me_after_login(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> None:
    await _login(api_client, mock_client)
    response = await api_client.get("/api/me")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"
    data = response.json()
    assert data["sub"] == "u-1001"
    assert data["nickname"] == "Alice"
    assert data["picture"] == "https://mock-idp.test/a.jpg"
    assert data["csrf_token"]


async def test_me_without_session_returns_401(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/me")
    assert response.status_code == 401


async def test_me_with_tampered_cookie_returns_401(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> None:
    await _login(api_client, mock_client)
    api_client.cookies.set("lichat_session", "bogus")
    response = await api_client.get("/api/me")
    assert response.status_code == 401


async def test_me_with_expired_session_returns_401(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _login(api_client, mock_client)
    session = (
        await db_session.execute(select(Session))
    ).scalars().one()
    session.expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    response = await api_client.get("/api/me")
    assert response.status_code == 401
