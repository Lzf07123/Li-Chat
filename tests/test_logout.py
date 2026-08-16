from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.models import Session
from app.sso.signing import sign_state
from tests.fixtures.chat import seed_session_sync


async def _login(api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/oidc/login")
    authorize = await mock_client.get(response.headers["location"])
    callback = await api_client.get(authorize.headers["location"])
    assert callback.status_code == 302


async def test_logout_redirects_to_end_session_and_clears_session(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _login(api_client, mock_client)
    me = (await api_client.get("/api/me")).json()
    response = await api_client.post("/oidc/logout", headers={"x-csrf-token": me["csrf_token"]})
    assert response.status_code == 302
    location = response.headers["location"]
    assert urlparse(location).path == "/oauth2/end-session"
    query = parse_qs(urlparse(location).query)
    assert query["id_token_hint"]
    assert query["client_id"] == ["test-client"]
    assert query["post_logout_redirect_uri"] == ["http://test/"]
    assert query["state"]
    assert (await db_session.execute(select(Session))).all() == []
    assert (await api_client.get("/api/me")).status_code == 401


async def test_logout_without_csrf_returns_403(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> None:
    await _login(api_client, mock_client)
    response = await api_client.post("/oidc/logout")
    assert response.status_code == 403


async def test_logout_accepts_csrf_form_field(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> None:
    await _login(api_client, mock_client)
    me = (await api_client.get("/api/me")).json()
    response = await api_client.post("/oidc/logout", data={"csrf_token": me["csrf_token"]})
    assert response.status_code == 302


async def test_logout_local_clears_session_without_end_session(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _login(api_client, mock_client)
    me = (await api_client.get("/api/me")).json()
    response = await api_client.post(
        "/oidc/logout-local", headers={"x-csrf-token": me["csrf_token"]}
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert (await db_session.execute(select(Session))).all() == []
    assert (await api_client.get("/api/me")).status_code == 401


async def test_logout_local_without_csrf_returns_403(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> None:
    await _login(api_client, mock_client)
    response = await api_client.post("/oidc/logout-local")
    assert response.status_code == 403


async def test_post_logout_accepts_valid_state(api_client: httpx.AsyncClient) -> None:
    signed = sign_state("test-session-secret", "token-1")
    response = await api_client.get("/oidc/post-logout", params={"state": signed})
    assert response.status_code == 302
    assert response.headers["location"] == "/"


async def test_post_logout_rejects_tampered_state(api_client: httpx.AsyncClient) -> None:
    signed = sign_state("test-session-secret", "token-1")
    response = await api_client.get("/oidc/post-logout", params={"state": signed + "x"})
    assert response.status_code == 400


async def test_post_logout_post_not_supported(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/oidc/post-logout", data={"state": "anything"})
    assert response.status_code == 405


def test_logout_disconnects_user_websocket(app) -> None:
    session_id, csrf = seed_session_sync(app, "u-1")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", session_id)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-1"}
            response = client.post(
                "/oidc/logout",
                headers={"x-csrf-token": csrf},
                follow_redirects=False,
            )
            assert response.status_code == 302
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_json()
            assert exc_info.value.code == 4401
