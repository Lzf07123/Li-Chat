from __future__ import annotations

from typing import Any

import httpx

from tests.fixtures.chat import make_friends, seed_session


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


async def _send(
    client: httpx.AsyncClient,
    csrf: str,
    content: str,
    *,
    reply_to_id: int | None = None,
) -> httpx.Response:
    body: dict[str, Any] = {"content": content}
    if reply_to_id is not None:
        body["reply_to_id"] = reply_to_id
    return await client.post(
        "/api/conversations/u-bob/messages",
        json=body,
        headers={"x-csrf-token": csrf},
    )


async def test_dm_reply_payload_and_history(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        original = await _send(alice, alice_csrf, "原文内容")
        original_id = original.json()["id"]
        replied = await bob.post(
            "/api/conversations/u-alice/messages",
            json={"content": "引用回复", "reply_to_id": original_id},
            headers={"x-csrf-token": bob_csrf},
        )
        assert replied.status_code == 201
        body = replied.json()
        history = await alice.get("/api/conversations/u-bob/messages")
    assert body["reply_to"]["id"] == original_id
    assert body["reply_to"]["content"] == "原文内容"
    history_item = history.json()["messages"][0]
    assert history_item["reply_to"]["sender_sub"] == "u-alice"


async def test_reply_validation(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, carol:
        original = await _send(alice, alice_csrf, "在 alice-bob 会话")
        other = await carol.post(
            "/api/conversations/u-alice/messages",
            json={"content": "hi", "reply_to_id": original.json()["id"]},
            headers={"x-csrf-token": carol_csrf},
        )
        missing = await _send(alice, alice_csrf, "hi", reply_to_id=999999)
        bad_param = await _send(alice, alice_csrf, "hi", reply_to_id=0)
    assert other.status_code == 404
    assert missing.status_code == 404
    assert bad_param.status_code == 422


async def test_reply_to_deleted_message_allowed(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        original = await _send(alice, alice_csrf, "将被撤回")
        original_id = original.json()["id"]
        removed = await alice.delete(
            f"/api/conversations/u-bob/messages/{original_id}",
            headers={"x-csrf-token": alice_csrf},
        )
        assert removed.status_code == 200
        replied = await bob.post(
            "/api/conversations/u-alice/messages",
            json={"content": "回复墓碑", "reply_to_id": original_id},
            headers={"x-csrf-token": bob_csrf},
        )
    assert replied.status_code == 201
    assert replied.json()["reply_to"]["deleted"] is True
    assert replied.json()["reply_to"]["content"] is None


async def test_group_reply_same_group_only(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        group_a = await alice.post(
            "/api/groups",
            json={"name": "群A", "member_subs": ["u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        group_b = await alice.post(
            "/api/groups",
            json={"name": "群B", "member_subs": ["u-bob", "u-carol"]},
            headers={"x-csrf-token": alice_csrf},
        )
        first = await bob.post(
            f"/api/groups/{group_a.json()['id']}/messages",
            json={"content": "群A消息"},
            headers={"x-csrf-token": bob_csrf},
        )
        same_group = await bob.post(
            f"/api/groups/{group_a.json()['id']}/messages",
            json={"content": "同群回复", "reply_to_id": first.json()["id"]},
            headers={"x-csrf-token": bob_csrf},
        )
        cross_group = await bob.post(
            f"/api/groups/{group_b.json()['id']}/messages",
            json={"content": "跨群回复", "reply_to_id": first.json()["id"]},
            headers={"x-csrf-token": bob_csrf},
        )
    assert same_group.status_code == 201
    assert same_group.json()["reply_to"]["content"] == "群A消息"
    assert cross_group.status_code == 404
