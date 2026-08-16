from __future__ import annotations

import asyncio
from typing import Any

from starlette.testclient import TestClient

from app.ws.calls import CallManager, handle_call
from tests.fixtures.chat import make_friends, seed_session_sync, seed_user


def _friends(app: Any, a: str, b: str) -> None:
    async def run() -> None:
        async with app.state.session_factory() as db:
            await make_friends(db, a, b)

    asyncio.run(run())


async def _seed_stranger(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-carol", nickname="Carol")


def test_call_state_machine_transitions() -> None:
    calls = CallManager()
    assert calls.offer("u-a", "u-b") is True
    assert calls.offer("u-a", "u-b") is False
    assert calls.answer("u-b", "u-a") is True
    assert calls.is_active("u-a", "u-b") is True
    assert calls.ice_allowed("u-a", "u-b", min_interval=0.1) is True
    assert calls.ice_allowed("u-a", "u-b", min_interval=0.1) is False
    calls.end("u-a", "u-b")
    assert calls.is_active("u-a", "u-b") is False
    assert calls.offer("u-a", "u-b") is True


def test_call_offer_answer_ice_end_flow_over_ws(app: Any) -> None:
    _friends(app, "u-alice", "u-bob")
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
                alice_ws.send_json(
                    {"type": "call", "op": "offer", "to": "u-bob", "payload": {"sdp": "offer"}}
                )
                offer = _receive_type(bob_ws, "call")
                assert offer["op"] == "offer"
                bob_ws.send_json(
                    {"type": "call", "op": "answer", "to": "u-alice", "payload": {"sdp": "answer"}}
                )
                answer = _receive_type(alice_ws, "call")
                bob_ws.send_json(
                    {"type": "call", "op": "ice", "to": "u-alice", "payload": {"candidate": "c1"}}
                )
                ice = _receive_type(alice_ws, "call")
                alice_ws.send_json(
                    {"type": "call", "op": "end", "to": "u-bob", "payload": {}}
                )
                ended = _receive_type(bob_ws, "call")
    assert answer["op"] == "answer"
    assert ice["payload"] == {"candidate": "c1"}
    assert ended["op"] == "end"


def test_call_busy_invalid_and_unavailable(app: Any) -> None:
    _friends(app, "u-alice", "u-bob")
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
                alice_ws.send_json(
                    {"type": "call", "op": "offer", "to": "u-bob", "payload": {}}
                )
                bob_ws.send_json(
                    {"type": "call", "op": "answer", "to": "u-alice", "payload": {}}
                )
                _receive_type(alice_ws, "call")
                # 通话进行中再次 offer → busy
                alice_ws.send_json(
                    {"type": "call", "op": "offer", "to": "u-bob", "payload": {}}
                )
                busy = _receive_type(alice_ws, "call")
                # 结束后的 answer → invalid
                alice_ws.send_json(
                    {"type": "call", "op": "end", "to": "u-bob", "payload": {}}
                )
                _receive_type(bob_ws, "call")
                alice_ws.send_json(
                    {"type": "call", "op": "answer", "to": "u-bob", "payload": {}}
                )
                invalid = _receive_type(alice_ws, "call")
    assert busy["op"] == "busy"
    assert invalid["op"] == "invalid"


def test_call_to_offline_friend_returns_unavailable(app: Any) -> None:
    _friends(app, "u-alice", "u-bob")
    alice_sid, _ = seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            alice_ws.send_json(
                {"type": "call", "op": "offer", "to": "u-bob", "payload": {}}
            )
            event = _receive_type(alice_ws, "call")
    assert event["op"] == "unavailable"


def test_call_to_stranger_is_dropped(app: Any) -> None:
    _friends(app, "u-alice", "u-bob")
    asyncio.run(_seed_stranger(app))
    alice_sid, _ = seed_session_sync(app, "u-alice")
    carol_sid, _ = seed_session_sync(app, "u-carol")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", carol_sid)
        with client.websocket_connect("/ws") as carol_ws:
            assert carol_ws.receive_json() == {"type": "hello", "sub": "u-carol"}
            client.cookies.set("lichat_session", alice_sid)
            with client.websocket_connect("/ws") as alice_ws:
                assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
                client.cookies.set("lichat_session", carol_sid)
                alice_ws.send_json(
                    {"type": "call", "op": "offer", "to": "u-carol", "payload": {}}
                )
                carol_ws.send_json({"type": "ping"})
                marker = carol_ws.receive_json()
    assert marker == {"type": "pong"}


def test_call_offer_relays_kind(app: Any) -> None:
    """offer 中继帧必须携带 kind，被叫端才能区分视频/语音。"""
    _friends(app, "u-alice", "u-bob")
    alice_sid, _ = seed_session_sync(app, "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            client.cookies.set("lichat_session", bob_sid)
            with client.websocket_connect("/ws") as bob_ws:
                assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
                alice_ws.send_json(
                    {
                        "type": "call",
                        "op": "offer",
                        "to": "u-bob",
                        "kind": "video",
                        "payload": {"type": "offer", "sdp": "v=0"},
                    }
                )
                offer = _receive_type(bob_ws, "call")
    assert offer["op"] == "offer"
    assert offer["kind"] == "video"
    assert offer["payload"] == {"type": "offer", "sdp": "v=0"}


def test_call_throttled_ice_dropped_silently(app: Any, monkeypatch: Any) -> None:
    """限频的 ICE 必须静默丢弃：双方都不应收到 invalid/error。"""
    _friends(app, "u-alice", "u-bob")
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
                alice_ws.send_json(
                    {"type": "call", "op": "offer", "to": "u-bob", "payload": {}}
                )
                _receive_type(bob_ws, "call")
                bob_ws.send_json(
                    {"type": "call", "op": "answer", "to": "u-alice", "payload": {}}
                )
                _receive_type(alice_ws, "call")
                monkeypatch.setattr(
                    app.state.call_manager,
                    "ice_allowed",
                    lambda *args, **kwargs: False,
                )
                alice_ws.send_json(
                    {
                        "type": "call",
                        "op": "ice",
                        "to": "u-bob",
                        "payload": {"candidate": "c1"},
                    }
                )
                alice_ws.send_json({"type": "ping"})
                assert alice_ws.receive_json() == {"type": "pong"}
                bob_ws.send_json({"type": "ping"})
                assert bob_ws.receive_json() == {"type": "pong"}


async def test_call_payload_size_limit(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-alice", "u-bob")
    manager = app.state.ws_manager
    calls = app.state.call_manager
    async with app.state.session_factory() as db:
        await handle_call(
            db,
            manager,
            calls,
            "u-alice",
            {
                "op": "offer",
                "to": "u-bob",
                "payload": {"sdp": "x" * 20_000},
            },
        )
    assert calls.is_active("u-alice", "u-bob") is False


def _receive_type(ws: Any, expected: str) -> dict[str, Any]:
    for _ in range(5):
        event = ws.receive_json()
        if event.get("type") == expected:
            return event
    raise AssertionError(f"expected ws event type {expected!r}")
