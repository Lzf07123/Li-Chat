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


async def _make_friends(app: Any, pairs: list[tuple[str, str]]) -> None:
    async with app.state.session_factory() as db:
        for a, b in pairs:
            await make_friends(db, a, b)


async def test_dm_mention_payload_and_history(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        sent = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "@bob 看这里", "mentions": ["u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert sent.status_code == 201
        history = await alice.get("/api/conversations/u-bob/messages")
        invalid = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "hi", "mentions": ["u-carol"]},
            headers={"x-csrf-token": alice_csrf},
        )
    assert sent.json()["mentions"] == ["u-bob"]
    assert history.json()["messages"][0]["mentions"] == ["u-bob"]
    assert invalid.status_code == 422


async def test_group_mentions_membership_dedupe_and_limit(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-alice", "u-carol"), ("u-bob", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        group = await alice.post(
            "/api/groups",
            json={"name": "提及群", "member_subs": ["u-bob", "u-carol"]},
            headers={"x-csrf-token": alice_csrf},
        )
        group_id = group.json()["id"]
        ok = await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "@bob @carol", "mentions": ["u-bob", "u-carol"]},
            headers={"x-csrf-token": alice_csrf},
        )
        dedupe = await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "@bob", "mentions": ["u-bob", "u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        outsider = await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "hi", "mentions": ["u-dave"]},
            headers={"x-csrf-token": alice_csrf},
        )
        too_many = await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "hi", "mentions": [f"u-{index}" for index in range(51)]},
            headers={"x-csrf-token": alice_csrf},
        )
    assert ok.status_code == 201
    assert ok.json()["mentions"] == ["u-bob", "u-carol"]
    assert dedupe.json()["mentions"] == ["u-bob"]
    assert outsider.status_code == 422
    assert too_many.status_code == 422


def test_mention_event_reaches_mentioned_member(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")

    async def setup() -> None:
        async with app.state.session_factory() as db:
            await make_friends(db, "u-alice", "u-bob")

    asyncio.run(setup())
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
                    json={"content": "@bob 来一下", "mentions": ["u-bob"]},
                    headers={"x-csrf-token": alice_csrf},
                )
                assert sent.status_code == 201
                bob_event = _receive_type(bob_ws, "message")
    assert bob_event["message"]["mentions"] == ["u-bob"]


def _receive_type(ws: Any, expected: str) -> dict[str, Any]:
    for _ in range(4):
        event = ws.receive_json()
        if event.get("type") == expected:
            return event
    raise AssertionError(f"expected ws event type {expected!r}")
