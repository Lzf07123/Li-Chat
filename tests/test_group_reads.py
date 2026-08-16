from __future__ import annotations

from typing import Any

import httpx

from tests.fixtures.chat import make_friends, seed_session, seed_user


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def test_group_message_readers(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-owner", "u-bob")
        await make_friends(db, "u-owner", "u-carol")
        await seed_user(db, "u-stranger", nickname="Stranger")
    owner_client, owner_csrf = await _client_for(app, "u-owner")
    created = await owner_client.post(
        "/api/groups",
        json={"name": "已读群", "member_subs": ["u-bob", "u-carol"]},
        headers={"x-csrf-token": owner_csrf},
    )
    assert created.status_code == 201
    group_id = created.json()["id"]
    sent = await owner_client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "看消息了没"},
        headers={"x-csrf-token": owner_csrf},
    )
    assert sent.status_code == 201
    message_id = sent.json()["id"]

    bob_client, bob_csrf = await _client_for(app, "u-bob")
    marked = await bob_client.post(
        f"/api/groups/{group_id}/read",
        json={"last_read_id": message_id},
        headers={"x-csrf-token": bob_csrf},
    )
    assert marked.status_code == 200

    readers = await owner_client.get(
        f"/api/groups/{group_id}/messages/{message_id}/reads"
    )
    assert readers.status_code == 200
    body = readers.json()
    assert body["read_count"] == 2
    assert body["total_members"] == 3
    assert {item["sub"] for item in body["readers"]} == {"u-owner", "u-bob"}

    history = await owner_client.get(f"/api/groups/{group_id}/messages")
    assert history.status_code == 200
    own = next(
        item for item in history.json()["messages"] if item["id"] == message_id
    )
    assert own["read_count"] == 2

    stranger_client, _ = await _client_for(app, "u-stranger")
    outside = await stranger_client.get(
        f"/api/groups/{group_id}/messages/{message_id}/reads"
    )
    assert outside.status_code == 404
    await owner_client.aclose()
    await bob_client.aclose()
    await stranger_client.aclose()
