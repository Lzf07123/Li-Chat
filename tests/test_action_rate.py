from __future__ import annotations

from typing import Any

import httpx

from app.sso.ratelimit import SlidingWindowRateLimiter
from tests.fixtures.chat import make_friends, seed_session


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def test_send_message_action_rate_limited(app: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        app.state, "action_limiter", SlidingWindowRateLimiter(3, 60)
    )
    async with app.state.session_factory() as db:
        await make_friends(db, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    for _ in range(3):
        response = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
        assert response.status_code == 201
    limited = await client.post(
        "/api/conversations/u-bob/messages",
        json={"content": "hi"},
        headers={"x-csrf-token": csrf},
    )
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    await client.aclose()


async def test_upload_action_rate_limited(app: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        app.state, "action_limiter", SlidingWindowRateLimiter(2, 60)
    )
    client, csrf = await _client_for(app, "u-alice")
    for _ in range(2):
        response = await client.post(
            "/api/uploads",
            files={"file": ("note.txt", b"hello", "text/plain")},
            headers={"x-csrf-token": csrf},
        )
        assert response.status_code == 201
    limited = await client.post(
        "/api/uploads",
        files={"file": ("note.txt", b"hello", "text/plain")},
        headers={"x-csrf-token": csrf},
    )
    assert limited.status_code == 429
    await client.aclose()
