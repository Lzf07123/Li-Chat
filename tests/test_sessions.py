from __future__ import annotations

from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.fixtures.chat import seed_session, seed_session_sync


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def test_list_sessions_with_current_flag(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    other_sid, _ = await seed_session(app, "u-alice")
    current_sid = client.cookies.get("lichat_session")
    async with client:
        response = await client.get("/api/me/sessions")
    body = response.json()
    assert response.status_code == 200
    by_id = {item["id"]: item for item in body["sessions"]}
    assert set(by_id) == {current_sid, other_sid}
    assert by_id[current_sid]["current"] is True
    assert by_id[other_sid]["current"] is False


async def test_revoke_other_session(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    other_sid, _ = await seed_session(app, "u-alice")
    async with client:
        revoked = await client.delete(
            f"/api/me/sessions/{other_sid}", headers={"x-csrf-token": csrf}
        )
        assert revoked.status_code == 200
        after = await client.get("/api/me/sessions")
    assert [item["id"] for item in after.json()["sessions"]] == [
        client.cookies.get("lichat_session")
    ]


async def test_revoke_foreign_session_404(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    bob_sid, _ = await seed_session(app, "u-bob")
    async with client:
        response = await client.delete(
            f"/api/me/sessions/{bob_sid}", headers={"x-csrf-token": csrf}
        )
    assert response.status_code == 404


async def test_revoke_all_others_keeps_current(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    await seed_session(app, "u-alice")
    await seed_session(app, "u-alice")
    current_sid = client.cookies.get("lichat_session")
    async with client:
        response = await client.delete("/api/me/sessions", headers={"x-csrf-token": csrf})
        assert response.status_code == 200
        after = await client.get("/api/me/sessions")
    assert [item["id"] for item in after.json()["sessions"]] == [current_sid]


def test_revoking_session_disconnects_its_websocket(app: Any) -> None:
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    victim_sid, _ = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", victim_sid)
        with client.websocket_connect("/ws") as victim_ws:
            assert victim_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            client.cookies.set("lichat_session", alice_sid)
            revoked = client.delete(
                f"/api/me/sessions/{victim_sid}", headers={"x-csrf-token": alice_csrf}
            )
            assert revoked.status_code == 200
            with pytest.raises(WebSocketDisconnect) as exc_info:
                victim_ws.receive_json()
    assert exc_info.value.code == 4401


async def test_sessions_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/me/sessions")
    assert response.status_code == 401
