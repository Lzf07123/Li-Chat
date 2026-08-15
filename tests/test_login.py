import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.fixtures.mock_idp import MockIdP


async def _start_login(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> str:
    response = await api_client.get("/oidc/login", params={"redirect_after": "/home"})
    assert response.status_code == 302
    authorize = await mock_client.get(response.headers["location"])
    assert authorize.status_code == 302
    return authorize.headers["location"]


async def test_login_creates_user_and_redirects(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    callback_url = await _start_login(api_client, mock_client)
    response = await api_client.get(callback_url)
    assert response.status_code == 302
    assert response.headers["location"] == "/home"
    user = (
        await db_session.execute(select(User).where(User.sub == "u-1001"))
    ).scalar_one()
    assert user.nickname == "Alice"
    assert user.picture == "https://mock-idp.test/a.jpg"


async def test_callback_with_unknown_state_rejected(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/oidc/callback", params={"code": "c", "state": "bogus"})
    assert response.status_code == 400


async def test_code_replay_rejected(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> None:
    callback_url = await _start_login(api_client, mock_client)
    first = await api_client.get(callback_url)
    assert first.status_code == 302
    second = await api_client.get(callback_url)
    assert second.status_code == 400


async def test_access_denied_shows_friendly_error(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/oidc/callback", params={"error": "access_denied", "state": "s"}
    )
    assert response.status_code == 302
    error_page = await api_client.get(response.headers["location"])
    assert error_page.status_code == 200
    assert "登录未完成" in error_page.json()["message"]


async def test_blocked_account_shows_friendly_error(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
    mock_idp: MockIdP,
    db_session: AsyncSession,
) -> None:
    mock_idp.blocked = True
    callback_url = await _start_login(api_client, mock_client)
    response = await api_client.get(callback_url)
    assert response.status_code == 302
    error_page = await api_client.get(response.headers["location"])
    assert error_page.status_code == 200
    assert "限制访问" in error_page.json()["message"]
    assert (await db_session.execute(select(User))).all() == []


async def test_open_redirect_parameter_is_ignored(
    api_client: httpx.AsyncClient, mock_client: httpx.AsyncClient
) -> None:
    response = await api_client.get(
        "/oidc/login", params={"redirect_after": "https://evil.example"}
    )
    authorize = await mock_client.get(response.headers["location"])
    callback = await api_client.get(authorize.headers["location"])
    assert callback.status_code == 302
    assert callback.headers["location"] == "/"


async def test_userinfo_sub_mismatch_rejected(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
    mock_idp: MockIdP,
    db_session: AsyncSession,
) -> None:
    mock_idp.token_sub = "u-9999"
    callback_url = await _start_login(api_client, mock_client)
    response = await api_client.get(callback_url)
    assert response.status_code == 401
    assert (await db_session.execute(select(User))).all() == []
