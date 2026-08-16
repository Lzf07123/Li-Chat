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


async def test_export_contains_my_visible_data(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-me", "u-bob")
    client, csrf = await _client_for(app, "u-me")
    sent = await client.post(
        "/api/conversations/u-bob/messages",
        json={"content": "export me"},
        headers={"x-csrf-token": csrf},
    )
    message_id = sent.json()["id"]
    starred = await client.put(
        f"/api/messages/{message_id}/star", headers={"x-csrf-token": csrf}
    )
    assert starred.status_code == 200
    created = await client.post(
        "/api/groups",
        json={"name": "导出群", "member_subs": ["u-bob"]},
        headers={"x-csrf-token": csrf},
    )
    group_id = created.json()["id"]
    group_sent = await client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "group export"},
        headers={"x-csrf-token": csrf},
    )
    assert group_sent.status_code == 201

    exported = await client.get("/api/me/export")
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].startswith("attachment;")
    body = exported.json()
    assert body["profile"]["sub"] == "u-me"
    assert any(friend["sub"] == "u-bob" for friend in body["friends"])
    assert any(item["content"] == "export me" for item in body["dm_messages"]["u-bob"])
    assert any(group["id"] == group_id for group in body["groups"])
    assert any(
        item["content"] == "group export"
        for item in body["group_messages"][str(group_id)]
    )
    assert any(item["id"] == message_id for item in body["stars"])
    await client.aclose()


async def test_export_requires_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/me/export")
    assert response.status_code == 401
