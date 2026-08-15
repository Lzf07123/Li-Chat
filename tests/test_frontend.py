import httpx


async def test_index_served(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Li&Chat" in response.text


async def test_static_asset_served(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


async def test_style_has_brand_tokens(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/style.css")
    assert response.status_code == 200
    assert "--chat-primary: #2563eb" in response.text
    assert "--chat-primary: #60a5fa" in response.text
    assert "prefers-reduced-motion" in response.text


async def test_brand_single_source(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/brand.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert 'name: "Li&Chat"' in response.text
    assert "一次登录，直连你的小圈子" in response.text
    assert 'icp: ""' in response.text


async def test_theme_script(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/theme.js")
    assert response.status_code == 200
    assert "chat-theme" in response.text
    assert "classList.toggle" in response.text


async def test_favicon_served(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/favicon.svg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]
    assert "<svg" in response.text


async def test_index_brand_chrome(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/")
    assert response.status_code == 200
    text = response.text
    assert 'rel="icon"' in text
    assert 'href="/favicon.svg"' in text
    assert 'name="theme-color"' in text
    assert "chat-theme" in text
    assert 'src="/brand.js"' in text
    assert 'src="/theme.js"' in text
    assert 'src="/ambient.js"' in text


async def test_app_script_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert 'href="/oidc/login"' in text
    assert "csrf_token" in text
    assert "4401" in text
    assert 'role="status"' in text
    assert "LiChatTheme.initTheme" in text


async def test_ambient_script(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/ambient.js")
    assert response.status_code == 200
    assert "canvas" in response.text
    assert "prefers-reduced-motion" in response.text


async def test_app_chat_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert "/api/friends" in text
    assert "/api/friends/requests" in text
    assert "/api/users/search" in text
    assert "/api/conversations/" in text
    assert '"message"' in text
    assert "friend_event" in text
    assert "encodeURIComponent" in text
    assert 'role="log"' in text
    assert "textContent" in text


async def test_app_header_profile_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert 'class="app-profile"' in text
    assert 'class="profile-name"' in text
    assert 'class="ws-status header-status"' in text
    assert "sidebar-status" not in text


async def test_chat_styles_present(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/style.css")
    assert response.status_code == 200
    text = response.text
    assert ".chat-sidebar" in text
    assert ".chat-panel" in text
    assert ".message-bubble" in text
    assert ".message-own" in text
    assert ".composer" in text
    assert ".sr-only" in text
    assert ".app-profile" in text
    assert ".header-status" in text
    assert "flex-wrap: wrap" in text
    assert "margin-left: auto" in text
    assert "max-width: 767px" in text
