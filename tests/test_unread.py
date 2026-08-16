from __future__ import annotations

import asyncio
from typing import Any

import httpx
from starlette.testclient import TestClient

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


def _summary_for(body: dict[str, Any], peer_sub: str) -> dict[str, Any]:
    return next(item for item in body["conversations"] if item["peer"]["sub"] == peer_sub)


async def test_sender_has_no_unread_recipient_has_one(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        sent = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "你好"},
            headers={"x-csrf-token": csrf},
        )
        assert sent.status_code == 201
        alice_summary = await client.get("/api/conversations")
    bob_client, _ = await _client_for(app, "u-bob")
    async with bob_client:
        bob_summary = await bob_client.get("/api/conversations")
    alice_item = _summary_for(alice_summary.json(), "u-bob")
    bob_item = _summary_for(bob_summary.json(), "u-alice")
    assert alice_item["unread_count"] == 0
    assert alice_item["last_message"]["content"] == "你好"
    assert alice_item["last_read_id"] == sent.json()["id"]
    assert bob_item["unread_count"] == 1
    assert bob_item["last_read_id"] == 0


async def test_unread_counts_are_per_conversation_and_sorted_by_last_activity(
    app: Any,
) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    await _make_friends(app, "u-alice", "u-carol")
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    carol_client, carol_csrf = await _client_for(app, "u-carol")
    async with bob_client, carol_client:
        first = await carol_client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "from carol"},
            headers={"x-csrf-token": carol_csrf},
        )
        await bob_client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "from bob 1"},
            headers={"x-csrf-token": bob_csrf},
        )
        await bob_client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "from bob 2"},
            headers={"x-csrf-token": bob_csrf},
        )
        assert first.status_code == 201
    alice_client, _ = await _client_for(app, "u-alice")
    async with alice_client:
        response = await alice_client.get("/api/conversations")
    body = response.json()
    assert [item["peer"]["sub"] for item in body["conversations"]] == [
        "u-bob",
        "u-carol",
    ]
    assert _summary_for(body, "u-bob")["unread_count"] == 2
    assert _summary_for(body, "u-carol")["unread_count"] == 1


async def test_mark_read_requires_friend_and_own_conversation_message(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-alice", "u-bob")
        await make_friends(db, "u-bob", "u-carol")
    alice_client, alice_csrf = await _client_for(app, "u-alice")
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    async with alice_client, bob_client:
        stranger = await alice_client.post(
            "/api/conversations/u-carol/read",
            json={"last_read_id": 1},
            headers={"x-csrf-token": alice_csrf},
        )
        sent = await bob_client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "m1"},
            headers={"x-csrf-token": bob_csrf},
        )
        own = await alice_client.post(
            "/api/conversations/u-bob/read",
            json={"last_read_id": sent.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        carol_sent = await bob_client.post(
            "/api/conversations/u-carol/messages",
            json={"content": "carol dm"},
            headers={"x-csrf-token": bob_csrf},
        )
        cross = await alice_client.post(
            "/api/conversations/u-bob/read",
            json={"last_read_id": carol_sent.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        missing = await alice_client.post(
            "/api/conversations/u-bob/read",
            json={"last_read_id": 999999},
            headers={"x-csrf-token": alice_csrf},
        )
    assert stranger.status_code == 403
    assert own.status_code == 200
    assert cross.status_code == 404
    assert missing.status_code == 404


async def test_read_cursor_only_moves_forward_and_clears_unread(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    async with bob_client:
        first = await bob_client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "m1"},
            headers={"x-csrf-token": bob_csrf},
        )
        second = await bob_client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "m2"},
            headers={"x-csrf-token": bob_csrf},
        )
        assert first.status_code == 201
        assert second.status_code == 201
    alice_client, alice_csrf = await _client_for(app, "u-alice")
    async with alice_client:
        partial = await alice_client.post(
            "/api/conversations/u-bob/read",
            json={"last_read_id": first.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert partial.status_code == 200
        after_partial = await alice_client.get("/api/conversations")
        assert _summary_for(after_partial.json(), "u-bob")["unread_count"] == 1
        full = await alice_client.post(
            "/api/conversations/u-bob/read",
            json={"last_read_id": second.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert full.status_code == 200
        backward = await alice_client.post(
            "/api/conversations/u-bob/read",
            json={"last_read_id": first.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert backward.status_code == 200
        final_summary = await alice_client.get("/api/conversations")
        assert _summary_for(final_summary.json(), "u-bob")["unread_count"] == 0
        assert (
            _summary_for(final_summary.json(), "u-bob")["last_read_id"]
            == second.json()["id"]
        )


def test_read_receipt_pushed_to_peer_over_ws(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")
    asyncio.run(_make_friends(app, "u-alice", "u-bob"))
    alice_sid, _ = seed_session_sync(app, "u-alice")
    bob_sid, bob_csrf = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            client.cookies.set("lichat_session", bob_sid)
            sent = client.post(
                "/api/conversations/u-alice/messages",
                json={"content": "实时"},
                headers={"x-csrf-token": bob_csrf},
            )
            assert sent.status_code == 201
            message_event = alice_ws.receive_json()
            read = client.post(
                "/api/conversations/u-alice/read",
                json={"last_read_id": sent.json()["id"]},
                headers={"x-csrf-token": bob_csrf},
            )
            assert read.status_code == 200
            receipt = alice_ws.receive_json()
    assert message_event["type"] == "message"
    assert receipt == {
        "type": "read_receipt",
        "by_sub": "u-bob",
        "peer_sub": "u-alice",
        "last_read_id": sent.json()["id"],
    }


async def test_conversations_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/conversations")
    assert response.status_code == 401
