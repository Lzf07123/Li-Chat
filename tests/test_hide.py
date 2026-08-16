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


async def test_hide_dm_message_only_for_self(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-alice", "u-bob")
    alice_client, alice_csrf = await _client_for(app, "u-alice")
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    sent = await alice_client.post(
        "/api/conversations/u-bob/messages",
        json={"content": "hello bob"},
        headers={"x-csrf-token": alice_csrf},
    )
    message_id = sent.json()["id"]

    hidden = await bob_client.delete(
        f"/api/conversations/u-alice/messages/{message_id}/me",
        headers={"x-csrf-token": bob_csrf},
    )
    assert hidden.status_code == 200
    again = await bob_client.delete(
        f"/api/conversations/u-alice/messages/{message_id}/me",
        headers={"x-csrf-token": bob_csrf},
    )
    assert again.status_code == 200

    bob_history = await bob_client.get("/api/conversations/u-alice/messages")
    assert all(item["id"] != message_id for item in bob_history.json()["messages"])
    alice_history = await alice_client.get("/api/conversations/u-bob/messages")
    assert any(item["id"] == message_id for item in alice_history.json()["messages"])
    await alice_client.aclose()
    await bob_client.aclose()


async def test_hide_group_message_scoped_to_viewer(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-owner", "u-bob")
        await make_friends(db, "u-owner", "u-carol")
    owner_client, owner_csrf = await _client_for(app, "u-owner")
    created = await owner_client.post(
        "/api/groups",
        json={"name": "隐藏测试群", "member_subs": ["u-bob", "u-carol"]},
        headers={"x-csrf-token": owner_csrf},
    )
    group_id = created.json()["id"]
    sent = await owner_client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "hide me"},
        headers={"x-csrf-token": owner_csrf},
    )
    message_id = sent.json()["id"]

    bob_client, bob_csrf = await _client_for(app, "u-bob")
    hidden = await bob_client.delete(
        f"/api/groups/{group_id}/messages/{message_id}/me",
        headers={"x-csrf-token": bob_csrf},
    )
    assert hidden.status_code == 200
    bob_history = await bob_client.get(f"/api/groups/{group_id}/messages")
    assert all(item["id"] != message_id for item in bob_history.json()["messages"])
    carol_client, _ = await _client_for(app, "u-carol")
    carol_history = await carol_client.get(f"/api/groups/{group_id}/messages")
    assert any(item["id"] == message_id for item in carol_history.json()["messages"])
    await owner_client.aclose()
    await bob_client.aclose()
    await carol_client.aclose()
