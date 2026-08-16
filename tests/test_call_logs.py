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


def _offer(ws: Any, target: str, kind: str = "audio") -> None:
    ws.send_json(
        {"type": "call", "op": "offer", "to": target, "kind": kind, "payload": {}}
    )


def test_accepted_call_logged(app: Any) -> None:
    asyncio.run(_make_friends(app, "u-alice", "u-bob"))
    alice_sid, _ = seed_session_sync(app, "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            client.cookies.set("lichat_session", bob_sid)
            with client.websocket_connect("/ws") as bob_ws:
                assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
                client.cookies.set("lichat_session", alice_sid)
                _offer(alice_ws, "u-bob", "video")
                _receive_type(bob_ws, "call")
                bob_ws.send_json(
                    {"type": "call", "op": "answer", "to": "u-alice", "payload": {}}
                )
                _receive_type(alice_ws, "call")
                alice_ws.send_json(
                    {"type": "call", "op": "end", "to": "u-bob", "payload": {}}
                )
                _receive_type(bob_ws, "call")
    async def check() -> None:
        client_for_alice, _ = await _client_for(app, "u-alice")
        async with client_for_alice:
            response = await client_for_alice.get("/api/me/calls")
            assert response.status_code == 200
            body = response.json()
            assert len(body["calls"]) == 1
            item = body["calls"][0]
            assert item["status"] == "accepted"
            assert item["kind"] == "video"
            assert item["peer"]["sub"] == "u-bob"
            assert item["ended_at"].endswith("Z")

    asyncio.run(check())


def test_missed_calls_logged_for_offline_and_busy(app: Any) -> None:
    asyncio.run(_make_friends(app, "u-alice", "u-bob"))
    alice_sid, _ = seed_session_sync(app, "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            # bob 在线，第一通响铃中；第二通应 busy → missed
            client.cookies.set("lichat_session", bob_sid)
            with client.websocket_connect("/ws") as bob_ws:
                assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
                client.cookies.set("lichat_session", alice_sid)
                _offer(alice_ws, "u-bob")
                _receive_type(bob_ws, "call")
                _offer(alice_ws, "u-bob")
                busy = _receive_type(alice_ws, "call")
                assert busy["op"] == "busy"
                alice_ws.send_json(
                    {"type": "call", "op": "end", "to": "u-bob", "payload": {}}
                )
                _receive_type(bob_ws, "call")
    async def check() -> None:
        client_for_alice, _ = await _client_for(app, "u-alice")
        async with client_for_alice:
            body = (await client_for_alice.get("/api/me/calls")).json()
            statuses = {item["status"] for item in body["calls"]}
            assert statuses == {"missed"}
            assert len(body["calls"]) == 2

    asyncio.run(check())


def test_rejected_call_logged(app: Any) -> None:
    asyncio.run(_make_friends(app, "u-alice", "u-bob"))
    alice_sid, _ = seed_session_sync(app, "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            client.cookies.set("lichat_session", bob_sid)
            with client.websocket_connect("/ws") as bob_ws:
                assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
                client.cookies.set("lichat_session", alice_sid)
                _offer(alice_ws, "u-bob")
                _receive_type(bob_ws, "call")
                bob_ws.send_json(
                    {"type": "call", "op": "reject", "to": "u-alice", "payload": {}}
                )
                _receive_type(alice_ws, "call")
    async def check() -> None:
        client_for_alice, _ = await _client_for(app, "u-alice")
        async with client_for_alice:
            item = (await client_for_alice.get("/api/me/calls")).json()["calls"][0]
            assert item["status"] == "rejected"

    asyncio.run(check())


async def test_calls_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/me/calls")
    assert response.status_code == 401


def _receive_type(ws: Any, expected: str) -> dict[str, Any]:
    for _ in range(5):
        event = ws.receive_json()
        if event.get("type") == expected:
            return event
    raise AssertionError(f"expected ws event type {expected!r}")
