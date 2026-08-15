from __future__ import annotations

import asyncio
from typing import Any

import httpx
from starlette.testclient import TestClient

from tests.fixtures.chat import (
    make_friends,
    seed_session,
    seed_session_sync,
    seed_user,
)


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


async def test_send_message_ok(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "你好 Bob"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["sender_sub"] == "u-alice"
    assert body["recipient_sub"] == "u-bob"
    assert body["content"] == "你好 Bob"
    assert body["created_at"].endswith("Z")


async def test_send_message_validation_errors(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        blank = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "   "},
            headers={"x-csrf-token": csrf},
        )
        too_long = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "x" * 2001},
            headers={"x-csrf-token": csrf},
        )
        self_message = await client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
        ghost = await client.post(
            "/api/conversations/u-ghost/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
    assert blank.status_code == 422
    assert too_long.status_code == 422
    assert self_message.status_code == 400
    assert ghost.status_code == 404


async def test_send_message_requires_friendship_and_csrf(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        no_friend = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
        no_csrf = await client.post(
            "/api/conversations/u-bob/messages", json={"content": "hi"}
        )
    assert no_friend.status_code == 403
    assert no_csrf.status_code == 403


async def test_history_desc_pagination_and_termination(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        for index in range(5):
            response = await client.post(
                "/api/conversations/u-bob/messages",
                json={"content": f"m{index}"},
                headers={"x-csrf-token": csrf},
            )
            assert response.status_code == 201
        first = await client.get(
            "/api/conversations/u-bob/messages", params={"limit": 2}
        )
        page = first.json()
        second = await client.get(
            "/api/conversations/u-bob/messages",
            params={"limit": 2, "before": page["next_before"]},
        )
        page2 = second.json()
        third = await client.get(
            "/api/conversations/u-bob/messages",
            params={"limit": 2, "before": page2["next_before"]},
        )
        page3 = third.json()
    assert [item["content"] for item in page["messages"]] == ["m4", "m3"]
    assert [item["content"] for item in page2["messages"]] == ["m2", "m1"]
    assert [item["content"] for item in page3["messages"]] == ["m0"]
    assert page3["next_before"] is None


async def test_history_visible_after_unfriend_and_stranger_empty(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    async with app.state.session_factory() as db:
        await seed_user(db, "u-carol", nickname="Carol")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        sent = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "留档"},
            headers={"x-csrf-token": csrf},
        )
        assert sent.status_code == 201
        removed = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
        assert removed.status_code == 200
        blocked = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
        history = await client.get("/api/conversations/u-bob/messages")
        stranger = await client.get("/api/conversations/u-carol/messages")
    assert blocked.status_code == 403
    assert history.status_code == 200
    assert [item["content"] for item in history.json()["messages"]] == ["留档"]
    assert stranger.status_code == 200
    assert stranger.json() == {"messages": [], "next_before": None}


async def test_history_parameter_validation(app: Any) -> None:
    client, _ = await _client_for(app, "u-alice")
    async with client:
        zero_limit = await client.get(
            "/api/conversations/u-bob/messages", params={"limit": 0}
        )
        bad_before = await client.get(
            "/api/conversations/u-bob/messages", params={"before": 0}
        )
    assert zero_limit.status_code == 422
    assert bad_before.status_code == 422


async def test_messages_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/conversations/u-bob/messages")
    assert response.status_code == 401


def test_message_pushed_to_both_parties_over_ws(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")

    async def run_friends() -> None:
        await _make_friends(app, "u-alice", "u-bob")

    asyncio.run(run_friends())
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as bob_ws:
            assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            with client.websocket_connect("/ws") as alice_ws:
                assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
                response = client.post(
                    "/api/conversations/u-bob/messages",
                    json={"content": "实时"},
                    headers={"x-csrf-token": alice_csrf},
                )
                assert response.status_code == 201
                alice_event = alice_ws.receive_json()
            bob_event = bob_ws.receive_json()
    assert alice_event["type"] == "message"
    assert alice_event["message"]["content"] == "实时"
    assert bob_event["type"] == "message"
    assert bob_event["message"]["content"] == "实时"
    assert bob_event["message"]["id"] == alice_event["message"]["id"]
