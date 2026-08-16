from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import httpx
from starlette.testclient import TestClient

from app.models import Message
from app.timeutil import utcnow
from tests.fixtures.chat import make_friends, seed_session, seed_session_sync


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def _make_friends(app: Any, a: str, b: str) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, a, b)


async def _send(app: Any, client: httpx.AsyncClient, csrf: str, content: str) -> int:
    response = await client.post(
        "/api/conversations/u-bob/messages",
        json={"content": content},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_edit_own_message_updates_content_and_timestamp(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        message_id = await _send(app, client, csrf, "原文")
        edited = await client.patch(
            f"/api/conversations/u-bob/messages/{message_id}",
            json={"content": "改过"},
            headers={"x-csrf-token": csrf},
        )
    assert edited.status_code == 200
    body = edited.json()
    assert body["content"] == "改过"
    assert body["edited_at"].endswith("Z")
    assert body["deleted"] is False
    bob_client, _ = await _client_for(app, "u-bob")
    async with bob_client:
        history = await bob_client.get("/api/conversations/u-alice/messages")
    item = history.json()["messages"][0]
    assert item["content"] == "改过"
    assert item["edited_at"].endswith("Z")


async def test_edit_permissions_window_and_validation(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        message_id = await _send(app, alice, alice_csrf, "原文")
        not_sender = await bob.patch(
            f"/api/conversations/u-alice/messages/{message_id}",
            json={"content": "越权"},
            headers={"x-csrf-token": bob_csrf},
        )
        missing = await alice.patch(
            "/api/conversations/u-bob/messages/999999",
            json={"content": "不存在"},
            headers={"x-csrf-token": alice_csrf},
        )
        blank = await alice.patch(
            f"/api/conversations/u-bob/messages/{message_id}",
            json={"content": "   "},
            headers={"x-csrf-token": alice_csrf},
        )
        async with app.state.session_factory() as db:
            message = await db.get(Message, message_id)
            assert message is not None
            message.created_at = utcnow() - timedelta(minutes=6)
            await db.commit()
        expired = await alice.patch(
            f"/api/conversations/u-bob/messages/{message_id}",
            json={"content": "超时"},
            headers={"x-csrf-token": alice_csrf},
        )
    assert not_sender.status_code == 403
    assert missing.status_code == 404
    assert blank.status_code == 422
    assert expired.status_code == 409


async def test_delete_produces_tombstone_and_clears_content(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        message_id = await _send(app, alice, alice_csrf, "要撤回的")
        deleted = await alice.delete(
            f"/api/conversations/u-bob/messages/{message_id}",
            headers={"x-csrf-token": alice_csrf},
        )
        assert deleted.status_code == 200
        body = deleted.json()
        assert body["deleted"] is True
        assert body["content"] is None
        edit_after = await alice.patch(
            f"/api/conversations/u-bob/messages/{message_id}",
            json={"content": "再改"},
            headers={"x-csrf-token": alice_csrf},
        )
        delete_again = await alice.delete(
            f"/api/conversations/u-bob/messages/{message_id}",
            headers={"x-csrf-token": alice_csrf},
        )
    assert edit_after.status_code == 409
    assert delete_again.status_code == 409
    bob, _ = await _client_for(app, "u-bob")
    async with bob:
        history = await bob.get("/api/conversations/u-alice/messages")
    item = history.json()["messages"][0]
    assert item["deleted"] is True
    assert item["content"] is None
    async with app.state.session_factory() as db:
        message = await db.get(Message, message_id)
        assert message is not None
        assert message.content == ""
        assert message.deleted_at is not None


def test_edit_and_delete_events_pushed_over_ws(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")

    async def run_friends() -> None:
        await _make_friends(app, "u-alice", "u-bob")

    asyncio.run(run_friends())
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            client.cookies.set("lichat_session", bob_sid)
            with client.websocket_connect("/ws") as bob_ws:
                assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
                client.cookies.set("lichat_session", alice_sid)
                sent = client.post(
                    "/api/conversations/u-bob/messages",
                    json={"content": "原文"},
                    headers={"x-csrf-token": alice_csrf},
                )
                assert sent.status_code == 201
                message_id = sent.json()["id"]
                _receive_type(alice_ws, "message")
                edited = client.patch(
                    f"/api/conversations/u-bob/messages/{message_id}",
                    json={"content": "改过"},
                    headers={"x-csrf-token": alice_csrf},
                )
                assert edited.status_code == 200
                alice_edit_event = _receive_type(alice_ws, "message_edited")
                bob_edit_event = _receive_type(bob_ws, "message_edited")
                removed = client.delete(
                    f"/api/conversations/u-bob/messages/{message_id}",
                    headers={"x-csrf-token": alice_csrf},
                )
                assert removed.status_code == 200
                alice_delete_event = _receive_type(alice_ws, "message_deleted")
                bob_delete_event = _receive_type(bob_ws, "message_deleted")
    assert alice_edit_event["message"]["content"] == "改过"
    assert bob_edit_event["message"]["content"] == "改过"
    assert alice_delete_event["message"]["deleted"] is True
    assert bob_delete_event["message"]["deleted"] is True


def _receive_type(ws: Any, expected: str) -> dict[str, Any]:
    for _ in range(4):
        event = ws.receive_json()
        if event.get("type") == expected:
            return event
    raise AssertionError(f"expected ws event type {expected!r}")
