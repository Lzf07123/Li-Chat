from __future__ import annotations

import asyncio
import time
from typing import Any

from starlette.testclient import TestClient

from app.ws.manager import ConnectionManager
from app.ws.relay import relay_typing
from tests.fixtures.chat import make_friends, seed_session_sync, seed_user


def _friends(app: Any, a: str, b: str) -> None:
    async def run() -> None:
        async with app.state.session_factory() as db:
            await make_friends(db, a, b)

    asyncio.run(run())


def test_presence_online_offline_reaches_friend_over_ws(app: Any) -> None:
    _friends(app, "u-alice", "u-bob")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as bob_ws:
            assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            alice_sid, _ = seed_session_sync(app, "u-alice")
            client.cookies.set("lichat_session", alice_sid)
            with client.websocket_connect("/ws") as alice_ws:
                assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
                online = bob_ws.receive_json()
                assert online == {"type": "presence", "sub": "u-alice", "online": True}
                alice_ws.close(1000)
                offline = bob_ws.receive_json()
    assert offline["type"] == "presence"
    assert offline["sub"] == "u-alice"
    assert offline["online"] is False
    assert offline["last_seen_at"].endswith("Z")


def test_friends_api_reports_online_and_last_seen(app: Any) -> None:
    _friends(app, "u-alice", "u-bob")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, _ = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        before = client.get("/api/friends").json()["friends"][0]
        assert before["online"] is False
        assert before["last_seen_at"] is None
        client.cookies.set("lichat_session", alice_sid)
        with client.websocket_connect("/ws") as alice_ws:
            assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
            client.cookies.set("lichat_session", bob_sid)
            during = client.get("/api/friends").json()["friends"][0]
            assert during["online"] is True
            alice_ws.close(1000)
        after = client.get("/api/friends").json()["friends"][0]
    assert after["online"] is False
    assert after["last_seen_at"] is not None
    assert after["last_seen_at"].endswith("Z")


def test_typing_relayed_between_friends_over_ws(app: Any) -> None:
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
                presence = alice_ws.receive_json()
                assert presence["type"] == "presence"
                bob_ws.send_json({"type": "typing", "to": "u-alice", "action": "start"})
                event = alice_ws.receive_json()
    assert event == {"type": "typing", "from": "u-bob", "action": "start"}


async def test_typing_rejected_for_strangers_and_bad_payload(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-carol", nickname="Carol")
    manager = app.state.ws_manager
    async with app.state.session_factory() as db:
        stranger = await relay_typing(
            db, manager, "u-alice", {"to": "u-carol", "action": "start"}
        )
        bad_action = await relay_typing(
            db, manager, "u-alice", {"to": "u-carol", "action": "spin"}
        )
        self_target = await relay_typing(
            db, manager, "u-alice", {"to": "u-alice", "action": "start"}
        )
    assert stranger is False
    assert bad_action is False
    assert self_target is False


def test_typing_rate_limit_window() -> None:
    manager = ConnectionManager()
    assert manager.typing_allowed("u-a", "u-b", min_interval=0.2) is True
    assert manager.typing_allowed("u-a", "u-b", min_interval=0.2) is False
    time.sleep(0.25)
    assert manager.typing_allowed("u-a", "u-b", min_interval=0.2) is True
