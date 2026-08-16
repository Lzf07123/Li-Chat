from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.sso.ratelimit import SlidingWindowRateLimiter
from tests.fixtures.mock_idp import MockIdP


def test_sliding_window_limiter_blocks_then_resets() -> None:
    limiter = SlidingWindowRateLimiter(limit=3, window=0.2)
    assert limiter.check("k") == (True, 0)
    assert limiter.check("k") == (True, 0)
    assert limiter.check("k") == (True, 0)
    allowed, retry_after = limiter.check("k")
    assert allowed is False
    assert retry_after >= 1
    time.sleep(0.25)
    assert limiter.check("k") == (True, 0)


def _make_app() -> Any:
    mock_idp = MockIdP()
    transport = httpx.ASGITransport(app=mock_idp.app)
    settings = Settings(
        _env_file=None,
        env="dev",
        database_url="sqlite+aiosqlite:///:memory:",
        oidc_issuer=mock_idp.ISSUER,
        oidc_discovery_url=f"{mock_idp.ISSUER}/.well-known/openid-configuration",
        oidc_client_id=mock_idp.client_id,
        oidc_client_secret=mock_idp.client_secret,
        oidc_redirect_uri="http://test/oidc/callback",
        oidc_post_logout_redirect_uri="http://test/",
        session_secret="test-session-secret",
        login_rate_limit=2,
        login_rate_window=60,
    )
    return create_app(settings, http_transport=transport)


def test_login_endpoint_returns_429_after_limit() -> None:
    app = _make_app()
    with TestClient(app) as client:
        first = client.get("/oidc/login", follow_redirects=False)
        second = client.get("/oidc/login", follow_redirects=False)
        third = client.get("/oidc/login", follow_redirects=False)
    assert first.status_code == 302
    assert second.status_code == 302
    assert third.status_code == 429
    assert int(third.headers["retry-after"]) >= 1


def test_callback_endpoint_shares_ip_bucket() -> None:
    app = _make_app()
    with TestClient(app) as client:
        first = client.get("/oidc/callback", params={"code": "x", "state": "y"})
        second = client.get("/oidc/callback", params={"code": "x", "state": "y"})
        third = client.get("/oidc/callback", params={"code": "x", "state": "y"})
    assert first.status_code == 400
    assert second.status_code == 400
    assert third.status_code == 429


def test_settings_validation() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, login_rate_limit=0)
    with pytest.raises(ValueError):
        Settings(_env_file=None, login_rate_window=0)
