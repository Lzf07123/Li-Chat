from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.fixtures.chat import make_friends_sync, seed_session_sync


def _receive(ws: Any, expected_type: str) -> dict[str, Any]:
    for _ in range(30):
        frame = ws.receive_json()
        if frame["type"] in {"presence", "typing"}:
            continue
        assert frame["type"] == expected_type, frame
        return frame
    raise AssertionError(f"never received {expected_type}")


def test_full_friend_dm_group_poll_mute_dissolve_flow(app: Any) -> None:
    make_friends_sync(app, "u-alice", "u-carol")
    alice_id, alice_csrf = seed_session_sync(app, "u-alice")
    bob_id, bob_csrf = seed_session_sync(app, "u-bob")
    carol_id, carol_csrf = seed_session_sync(app, "u-carol")

    with (
        TestClient(app) as alice,
        TestClient(app) as bob,
        TestClient(app) as carol,
    ):
        alice.cookies.set("lichat_session", alice_id)
        bob.cookies.set("lichat_session", bob_id)
        carol.cookies.set("lichat_session", carol_id)
        with (
            alice.websocket_connect("/ws") as alice_ws,
            bob.websocket_connect("/ws") as bob_ws,
            carol.websocket_connect("/ws") as carol_ws,
        ):
            assert _receive(alice_ws, "hello")["sub"] == "u-alice"
            assert _receive(bob_ws, "hello")["sub"] == "u-bob"
            assert _receive(carol_ws, "hello")["sub"] == "u-carol"

            requested = alice.post(
                "/api/friends/requests",
                json={"to_sub": "u-bob", "message": "我是 Alice"},
                headers={"x-csrf-token": alice_csrf},
            )
            assert requested.status_code == 201
            _receive(bob_ws, "friend_event")
            _receive(bob_ws, "notification")

            accepted = bob.post(
                "/api/friends/requests/u-alice/accept",
                headers={"x-csrf-token": bob_csrf},
            )
            assert accepted.status_code == 200
            _receive(alice_ws, "friend_event")

            sent = alice.post(
                "/api/conversations/u-bob/messages",
                json={"content": "你好 Bob"},
                headers={"x-csrf-token": alice_csrf},
            )
            assert sent.status_code == 201
            _receive(bob_ws, "message")
            _receive(alice_ws, "message")

            read = bob.post(
                "/api/conversations/u-alice/read",
                json={"last_read_id": sent.json()["id"]},
                headers={"x-csrf-token": bob_csrf},
            )
            assert read.status_code == 200
            _receive(alice_ws, "read_receipt")

            created = alice.post(
                "/api/groups",
                json={"name": "全家桶", "member_subs": ["u-bob", "u-carol"]},
                headers={"x-csrf-token": alice_csrf},
            )
            assert created.status_code == 201
            group_id = created.json()["id"]
            for ws in (alice_ws, bob_ws, carol_ws):
                _receive(ws, "group_event")

            mention = alice.post(
                f"/api/groups/{group_id}/messages",
                json={"content": "开会 @Carol", "mentions": ["u-carol"]},
                headers={"x-csrf-token": alice_csrf},
            )
            assert mention.status_code == 201
            _receive(alice_ws, "message")
            _receive(bob_ws, "message")
            _receive(carol_ws, "message")
            _receive(carol_ws, "notification")

            poll = alice.post(
                f"/api/groups/{group_id}/messages",
                json={
                    "content": "",
                    "content_type": "poll",
                    "poll": {"question": "聚餐吗", "options": ["去", "不去"]},
                },
                headers={"x-csrf-token": alice_csrf},
            )
            assert poll.status_code == 201
            _receive(alice_ws, "message")
            _receive(bob_ws, "message")
            _receive(carol_ws, "message")
            poll_id = poll.json()["poll"]["id"]
            voted = bob.put(
                f"/api/groups/{group_id}/polls/{poll_id}/vote",
                json={"option_indexes": [0]},
                headers={"x-csrf-token": bob_csrf},
            )
            assert voted.status_code == 200
            for ws in (alice_ws, bob_ws, carol_ws):
                _receive(ws, "poll_event")

            muted = alice.patch(
                f"/api/groups/{group_id}/members/u-carol/mute",
                json={"muted": True},
                headers={"x-csrf-token": alice_csrf},
            )
            assert muted.status_code == 200
            for ws in (alice_ws, bob_ws, carol_ws):
                frame = _receive(ws, "group_event")
                assert frame["event"] == "member_muted"
            _receive(carol_ws, "notification")
            blocked = carol.post(
                f"/api/groups/{group_id}/messages",
                json={"content": "被禁言了"},
                headers={"x-csrf-token": carol_csrf},
            )
            assert blocked.status_code == 403

            dissolved = alice.post(
                f"/api/groups/{group_id}/dissolve",
                headers={"x-csrf-token": alice_csrf},
            )
            assert dissolved.status_code == 200
            for ws in (alice_ws, bob_ws, carol_ws):
                frame = _receive(ws, "group_event")
                assert frame["event"] == "dissolved"
                _receive(ws, "notification")
            gone = carol.get(f"/api/groups/{group_id}")
            assert gone.status_code == 404
