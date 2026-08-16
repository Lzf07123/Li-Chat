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
    assert "--chat-primary: #25786d" in response.text
    assert "--chat-primary: #7fd4c6" in response.text
    assert "--chat-accent-ice: #2f678f" in response.text
    assert "--chat-primary-soft-solid: #d9f4ee" in response.text
    assert "--chat-bg: #3a3f45" in response.text
    assert "var(--chat-success-soft-solid, var(--chat-success-soft))" in response.text
    assert "@keyframes tech-grid-drift" in response.text
    assert "@keyframes tech-beam-sweep" in response.text
    assert "@keyframes tech-dot-breathe" in response.text
    assert "@keyframes aurora-drift-1" in response.text
    assert ".tech-soft" in response.text
    assert ".aurora-soft" in response.text
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
    assert 'class="tech-ambience"' in text
    assert 'class="tech-grid"' in text
    assert 'class="aurora"' in text
    assert text.count('class="tech-beam"') == 3
    assert text.count('class="tech-dot"') == 8


async def test_app_script_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert 'href="/oidc/login"' in text
    assert "csrf_token" in text
    assert "4401" in text
    assert 'role="status"' in text
    assert "LiChatTheme.initTheme" in text
    assert 'window.location.href = "/"' in text
    assert 'window.location.href = "/oidc/login"' not in text
    assert '"pageshow"' in text


async def test_logout_modal_offers_two_logout_semantics(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/app.js")
    text = response.text
    assert 'id="logout-modal"' in text
    assert 'id="logout-local"' in text
    assert 'id="logout-sso"' in text
    assert 'submitLogoutForm("/oidc/logout-local")' in text
    assert 'submitLogoutForm("/oidc/logout")' in text
    assert "event.persisted" in text
    assert "state.loggingOut = true" in text


async def test_effect_layers_soften_outside_auth_shell(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/app.js")
    text = response.text
    assert 'classList.toggle("aurora-soft"' in text
    assert 'classList.toggle("tech-soft"' in text


async def test_ambient_script(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/ambient.js")
    assert response.status_code == 200
    assert "canvas" in response.text
    assert "prefers-reduced-motion" in response.text
    assert "is-typing" in response.text
    assert "wind" in response.text


async def test_v12_full_adoption_contracts(api_client: httpx.AsyncClient) -> None:
    css = (await api_client.get("/style.css")).text
    app = (await api_client.get("/app.js")).text
    for marker in [
        "--ease-in",
        ".card-signature",
        "@keyframes chat-signature-border",
        ".flow-line",
        "@keyframes chat-flow-line",
        ".btn-ripple",
        "@keyframes chat-btn-ripple",
        ".blur-unit",
        "@keyframes chat-blur-in",
        ".input-sm",
    ]:
        assert marker in css
    for marker in [
        "initMotionEffects",
        "blurText",
        "countUp",
        'class="flow-line"',
        "card-signature",
        "btn-ripple",
    ]:
        assert marker in app


async def test_static_assets_force_revalidation(api_client: httpx.AsyncClient) -> None:
    for path in ["/", "/app.js", "/style.css", "/brand.js", "/theme.js", "/ambient.js"]:
        response = await api_client.get(path)
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-cache"


async def test_oidc_error_page_brand_chrome(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/oidc-error.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    text = response.text
    assert 'id="error-message"' in text
    assert 'href="/oidc/login"' in text
    assert 'href="/"' in text
    assert 'src="/brand.js"' in text
    assert "auth-card" in text
    assert "card-signature" in text


async def test_app_chat_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert "/api/friends" in text
    assert "/api/friends/requests" in text
    assert "/api/search?kind=contacts" in text
    assert "/api/version" in text
    assert "FRONTEND_VERSION" in text
    assert "location.reload" in text
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
    assert 'id="profile-toggle"' in text
    assert 'aria-haspopup="menu"' in text
    assert 'class="profile-dropdown"' in text
    assert 'role="menuitem"' in text
    header = text.split("function headerHtml()", 1)[1]
    assert (
        header.index('class="app-profile"')
        < header.index('id="logout"')
        < header.index("themeToggleHtml()")
    )


async def test_app_recommendations_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert 'id="recommend-list"' in text
    assert 'id="recommend-refresh"' in text
    assert 'aria-label="刷新推荐"' in text
    assert "/api/friends/recommendations" in text


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
    assert ".profile-toggle" in text
    assert ".profile-dropdown" in text
    assert ".profile-menu-item" in text
    assert ".refresh-btn" in text
    assert "flex-wrap: wrap" in text
    assert "margin-left: auto" in text
    assert "max-width: 767px" in text
