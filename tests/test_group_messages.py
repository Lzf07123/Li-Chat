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


async def _create_group(
    app: Any, client: httpx.AsyncClient, csrf: str, name: str, members: list[str]
) -> int:
    response = await client.post(
        "/api/groups",
        json={"name": name, "member_subs": members},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _send_group(
    client: httpx.AsyncClient, csrf: str, group_id: int, content: str
) -> httpx.Response:
    return await client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": content},
        headers={"x-csrf-token": csrf},
    )


async def test_group_send_history_and_permissions(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, bob, carol:
        group_id = await _create_group(app, alice, alice_csrf, "群聊", ["u-bob"])
        sent = await _send_group(bob, bob_csrf, group_id, "大家好")
        assert sent.status_code == 201
        body = sent.json()
        assert body["group_id"] == group_id
        assert body["sender_sub"] == "u-bob"
        history = await alice.get(f"/api/groups/{group_id}/messages")
        outsider_send = await _send_group(carol, carol_csrf, group_id, "闯进来")
        outsider_history = await carol.get(f"/api/groups/{group_id}/messages")
    assert history.status_code == 200
    assert [item["content"] for item in history.json()["messages"]] == ["大家好"]
    assert outsider_send.status_code == 403
    assert outsider_history.status_code == 404


async def test_group_history_pagination(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        group_id = await _create_group(app, alice, alice_csrf, "分页", ["u-bob"])
        for index in range(5):
            assert (await _send_group(bob, bob_csrf, group_id, f"m{index}")).status_code == 201
        first = await alice.get(f"/api/groups/{group_id}/messages", params={"limit": 2})
        page = first.json()
        second = await alice.get(
            f"/api/groups/{group_id}/messages",
            params={"limit": 2, "before": page["next_before"]},
        )
    assert [item["content"] for item in page["messages"]] == ["m4", "m3"]
    assert [item["content"] for item in second.json()["messages"]] == ["m2", "m1"]


async def test_group_unread_and_read_cursor(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-alice", "u-carol"), ("u-bob", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, bob, carol:
        group_id = await _create_group(
            app, alice, alice_csrf, "未读", ["u-bob", "u-carol"]
        )
        first = await _send_group(bob, bob_csrf, group_id, "b1")
        second = await _send_group(carol, carol_csrf, group_id, "c1")
        summary = await alice.get("/api/conversations")
        item = next(
            conv for conv in summary.json()["conversations"] if conv["group"]
        )
        assert item["group"]["id"] == group_id
        assert item["unread_count"] == 2
        partial = await alice.post(
            f"/api/groups/{group_id}/read",
            json={"last_read_id": first.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert partial.status_code == 200
        after_partial = await alice.get("/api/conversations")
        item = next(conv for conv in after_partial.json()["conversations"] if conv["group"])
        assert item["unread_count"] == 1
        full = await alice.post(
            f"/api/groups/{group_id}/read",
            json={"last_read_id": second.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert full.status_code == 200
        backward = await alice.post(
            f"/api/groups/{group_id}/read",
            json={"last_read_id": first.json()["id"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert backward.status_code == 200
        final = await alice.get("/api/conversations")
        outsider_read = await bob.post(
            f"/api/groups/{group_id + 100}/read",
            json={"last_read_id": 1},
            headers={"x-csrf-token": bob_csrf},
        )
    item = next(conv for conv in final.json()["conversations"] if conv["group"])
    assert item["unread_count"] == 0
    assert item["last_read_id"] == second.json()["id"]
    assert outsider_read.status_code == 404


async def test_group_summary_disappears_after_leave(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        group_id = await _create_group(app, alice, alice_csrf, "退群", ["u-bob"])
        await _send_group(bob, bob_csrf, group_id, "你好")
        leave = await bob.post(
            f"/api/groups/{group_id}/leave", headers={"x-csrf-token": bob_csrf}
        )
        assert leave.status_code == 200
        bob_summary = await bob.get("/api/conversations")
        alice_summary = await alice.get("/api/conversations")
    assert all(
        conv["group"] is None for conv in bob_summary.json()["conversations"]
    )
    assert any(conv["group"] for conv in alice_summary.json()["conversations"])


def test_group_message_and_read_receipt_broadcast_over_ws(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")
    seed_session_sync(app, "u-carol")

    async def run_setup() -> int:
        async with app.state.session_factory() as db:
            await make_friends(db, "u-alice", "u-bob")
            await make_friends(db, "u-alice", "u-carol")
        from app.groups.service import create_group

        async with app.state.session_factory() as db:
            group = await create_group(db, "u-alice", "群", ["u-bob", "u-carol"])
            return group["id"]

    group_id = asyncio.run(run_setup())
    bob_sid, bob_csrf = seed_session_sync(app, "u-bob")
    carol_sid, _ = seed_session_sync(app, "u-carol")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as bob_ws:
            assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", carol_sid)
            with client.websocket_connect("/ws") as carol_ws:
                assert carol_ws.receive_json() == {"type": "hello", "sub": "u-carol"}
                client.cookies.set("lichat_session", bob_sid)
                sent = client.post(
                    f"/api/groups/{group_id}/messages",
                    json={"content": "群发"},
                    headers={"x-csrf-token": bob_csrf},
                )
                assert sent.status_code == 201
                message_id = sent.json()["id"]
                carol_message = _receive_type(carol_ws, "message")
                bob_message = _receive_type(bob_ws, "message")
                read = client.post(
                    f"/api/groups/{group_id}/read",
                    json={"last_read_id": message_id},
                    headers={"x-csrf-token": bob_csrf},
                )
                assert read.status_code == 200
                carol_receipt = _receive_type(carol_ws, "read_receipt")
    assert carol_message["message"]["group_id"] == group_id
    assert bob_message["message"]["content"] == "群发"
    assert carol_receipt["group_id"] == group_id


def _receive_type(ws: Any, expected: str) -> dict[str, Any]:
    for _ in range(5):
        event = ws.receive_json()
        if event.get("type") == expected:
            return event
    raise AssertionError(f"expected ws event type {expected!r}")
