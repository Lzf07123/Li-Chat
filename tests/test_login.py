from urllib.parse import parse_qs, unquote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, User
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
    session = (await db_session.execute(select(Session))).scalar_one()
    assert session.id_token


async def test_callback_with_unknown_state_rejected(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/oidc/callback", params={"code": "c", "state": "bogus"})
    assert response.status_code == 400


async def test_login_reuses_pending_state_for_same_browser(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
) -> None:
    first = await api_client.get("/oidc/login")
    assert first.status_code == 302
    assert api_client.cookies.get("lichat_auth") is not None
    second = await api_client.get("/oidc/login")
    assert second.status_code == 302
    first_state = parse_qs(urlparse(first.headers["location"]).query)["state"][0]
    second_state = parse_qs(urlparse(second.headers["location"]).query)["state"][0]
    assert second_state == first_state


async def test_completing_login_discards_other_authorizations(
    api_client: httpx.AsyncClient,
    mock_client: httpx.AsyncClient,
) -> None:
    first = await api_client.get("/oidc/login")
    authorize_url = first.headers["location"]
    authorize = await mock_client.get(authorize_url)
    callback = await api_client.get(authorize.headers["location"])
    assert callback.status_code == 302
    assert api_client.cookies.get("lichat_auth") is None
    authorize_again = await mock_client.get(authorize_url)
    second_callback = await api_client.get(authorize_again.headers["location"])
    assert second_callback.status_code == 400


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
    assert "message=" in response.headers["location"]
    assert "登录未完成" in unquote(response.headers["location"])
    error_page = await api_client.get(response.headers["location"])
    assert error_page.status_code == 200
    assert "text/html" in error_page.headers["content-type"]
    assert "登录未完成" in error_page.text
    assert "重新登录" in error_page.text
    assert "返回首页" in error_page.text


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
    assert "限制访问" in unquote(response.headers["location"])
    error_page = await api_client.get(response.headers["location"])
    assert error_page.status_code == 200
    assert "text/html" in error_page.headers["content-type"]
    assert "重新登录" in error_page.text
    assert (await db_session.execute(select(User))).all() == []


async def test_error_page_renders_message_safely(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/oidc/error", params={"message": "<script>alert(1)</script>"}
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers.get("cache-control") == "no-store"
    # 页面用 textContent 渲染 ?message=，服务端不做任何字符串拼接
    assert "<script>alert(1)</script>" not in response.text
    assert "textContent = message" in response.text


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
