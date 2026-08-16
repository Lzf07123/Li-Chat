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


async def test_archive_and_restore_dm_conversation(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-me", "u-bob")
    client, csrf = await _client_for(app, "u-me")
    key = ":".join(sorted(["u-me", "u-bob"]))
    archived = await client.patch(
        "/api/conversations/settings",
        json={"kind": "dm", "key": key, "archived": True},
        headers={"x-csrf-token": csrf},
    )
    assert archived.status_code == 200
    assert archived.json()["archived"] is True

    normal = await client.get("/api/conversations")
    assert all(item["peer"]["sub"] != "u-bob" for item in normal.json()["conversations"])
    hidden = await client.get("/api/conversations", params={"archived": "true"})
    assert [item["peer"]["sub"] for item in hidden.json()["conversations"]] == ["u-bob"]

    restored = await client.patch(
        "/api/conversations/settings",
        json={"kind": "dm", "key": key, "archived": False},
        headers={"x-csrf-token": csrf},
    )
    assert restored.status_code == 200
    back = await client.get("/api/conversations")
    assert any(
        item["peer"]["sub"] == "u-bob" for item in back.json()["conversations"]
    )
    await client.aclose()


async def test_archive_requires_valid_ownership(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-me", "u-bob")
    client, csrf = await _client_for(app, "u-me")
    bad_key = ":".join(sorted(["u-bob", "u-ghost"]))
    response = await client.patch(
        "/api/conversations/settings",
        json={"kind": "dm", "key": bad_key, "archived": True},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 404
    empty = await client.patch(
        "/api/conversations/settings",
        json={"kind": "dm", "key": ":".join(sorted(["u-me", "u-bob"]))},
        headers={"x-csrf-token": csrf},
    )
    assert empty.status_code == 422
    await client.aclose()
