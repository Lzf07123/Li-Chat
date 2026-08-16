from __future__ import annotations

import asyncio
from typing import Any

import httpx
from starlette.testclient import TestClient

from tests.fixtures.chat import make_friends, seed_session, seed_session_sync, seed_user


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


async def _send(
    app: Any, client: httpx.AsyncClient, csrf: str, content: str, to: str = "u-bob"
) -> int:
    response = await client.post(
        f"/api/conversations/{to}/messages",
        json={"content": content},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_add_reaction_idempotent_and_visible_in_history(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        message_id = await _send(app, alice, alice_csrf, "你好")
        first = await alice.put(
            f"/api/conversations/u-bob/messages/{message_id}/reactions",
            json={"emoji": "👍"},
            headers={"x-csrf-token": alice_csrf},
        )
        second = await alice.put(
            f"/api/conversations/u-bob/messages/{message_id}/reactions",
            json={"emoji": "👍"},
            headers={"x-csrf-token": alice_csrf},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["count"] == 1
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with bob:
        await bob.put(
            f"/api/conversations/u-alice/messages/{message_id}/reactions",
            json={"emoji": "👍"},
            headers={"x-csrf-token": bob_csrf},
        )
        history = await bob.get("/api/conversations/u-alice/messages")
    item = history.json()["messages"][0]
    assert item["reactions"] == [{"emoji": "👍", "count": 2}]
    assert item["my_reactions"] == ["👍"]


async def test_remove_reaction_and_my_reaction_for_other_user(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        message_id = await _send(app, alice, alice_csrf, "你好")
        await alice.put(
            f"/api/conversations/u-bob/messages/{message_id}/reactions",
            json={"emoji": "❤️"},
            headers={"x-csrf-token": alice_csrf},
        )
        removed = await alice.delete(
            f"/api/conversations/u-bob/messages/{message_id}/reactions?emoji=❤️",
            headers={"x-csrf-token": alice_csrf},
        )
        idempotent = await alice.delete(
            f"/api/conversations/u-bob/messages/{message_id}/reactions?emoji=❤️",
            headers={"x-csrf-token": alice_csrf},
        )
    assert removed.status_code == 200
    assert removed.json()["count"] == 0
    assert idempotent.status_code == 200
    bob, _ = await _client_for(app, "u-bob")
    async with bob:
        history = await bob.get("/api/conversations/u-alice/messages")
    item = history.json()["messages"][0]
    assert item["reactions"] == []
    assert item["my_reactions"] == []


async def test_reaction_permission_and_validation(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    await _make_friends(app, "u-alice", "u-carol")
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
        await seed_user(db, "u-carol", nickname="Carol")
    alice, alice_csrf = await _client_for(app, "u-alice")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, carol:
        message_id = await _send(app, alice, alice_csrf, "仅你我")
        outsider = await carol.put(
            f"/api/conversations/u-bob/messages/{message_id}/reactions",
            json={"emoji": "👍"},
            headers={"x-csrf-token": carol_csrf},
        )
        too_long = await alice.put(
            f"/api/conversations/u-bob/messages/{message_id}/reactions",
            json={"emoji": "🙂🙂🙂🙂🙂🙂🙂🙂🙂"},
            headers={"x-csrf-token": alice_csrf},
        )
        whitespace = await alice.put(
            f"/api/conversations/u-bob/messages/{message_id}/reactions",
            json={"emoji": " a b "},
            headers={"x-csrf-token": alice_csrf},
        )
    assert outsider.status_code == 404
    assert too_long.status_code == 422
    assert whitespace.status_code == 422


async def test_reaction_on_deleted_message_rejected(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        message_id = await _send(app, alice, alice_csrf, "将撤回")
        deleted = await alice.delete(
            f"/api/conversations/u-bob/messages/{message_id}",
            headers={"x-csrf-token": alice_csrf},
        )
        assert deleted.status_code == 200
        reaction = await alice.put(
            f"/api/conversations/u-bob/messages/{message_id}/reactions",
            json={"emoji": "👍"},
            headers={"x-csrf-token": alice_csrf},
        )
    assert reaction.status_code == 409


def test_reaction_events_pushed_to_both_parties_over_ws(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")
    asyncio.run(_make_friends(app, "u-alice", "u-bob"))
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
                    json={"content": "来回应"},
                    headers={"x-csrf-token": alice_csrf},
                )
                assert sent.status_code == 201
                message_id = sent.json()["id"]
                _receive_type(alice_ws, "message")
                reacted = client.put(
                    f"/api/conversations/u-bob/messages/{message_id}/reactions",
                    json={"emoji": "😮"},
                    headers={"x-csrf-token": alice_csrf},
                )
                assert reacted.status_code == 200
                alice_event = _receive_type(alice_ws, "message_reaction")
                bob_event = _receive_type(bob_ws, "message_reaction")
    assert alice_event["action"] == "added"
    assert alice_event["emoji"] == "😮"
    assert alice_event["count"] == 1
    assert bob_event["message_id"] == message_id


def _receive_type(ws: Any, expected: str) -> dict[str, Any]:
    for _ in range(4):
        event = ws.receive_json()
        if event.get("type") == expected:
            return event
    raise AssertionError(f"expected ws event type {expected!r}")
