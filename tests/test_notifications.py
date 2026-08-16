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


async def test_friend_request_creates_notification_and_mark_read(app: Any) -> None:
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    alice_client, alice_csrf = await _client_for(app, "u-alice")
    sent = await alice_client.post(
        "/api/friends/requests",
        json={"to_sub": "u-bob"},
        headers={"x-csrf-token": alice_csrf},
    )
    assert sent.status_code == 201

    listing = await bob_client.get("/api/me/notifications")
    assert listing.status_code == 200
    body = listing.json()
    assert body["unread_count"] == 1
    item = body["notifications"][0]
    assert item["type"] == "friend_request"
    assert item["actor"]["sub"] == "u-alice"
    assert item["read"] is False

    marked = await bob_client.post(
        "/api/me/notifications/read", headers={"x-csrf-token": bob_csrf}
    )
    assert marked.status_code == 200
    after = await bob_client.get("/api/me/notifications")
    assert after.json()["unread_count"] == 0
    assert after.json()["notifications"][0]["read"] is True
    await alice_client.aclose()
    await bob_client.aclose()


async def test_mention_mute_and_role_notifications(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-owner", "u-bob")
    owner_client, owner_csrf = await _client_for(app, "u-owner")
    created = await owner_client.post(
        "/api/groups",
        json={"name": "通知群", "member_subs": ["u-bob"]},
        headers={"x-csrf-token": owner_csrf},
    )
    group_id = created.json()["id"]
    mentioned = await owner_client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "hi", "mentions": ["u-bob"]},
        headers={"x-csrf-token": owner_csrf},
    )
    assert mentioned.status_code == 201
    muted = await owner_client.patch(
        f"/api/groups/{group_id}/members/u-bob/mute",
        json={"muted": True},
        headers={"x-csrf-token": owner_csrf},
    )
    assert muted.status_code == 200
    promoted = await owner_client.patch(
        f"/api/groups/{group_id}/members/u-bob",
        json={"role": "admin"},
        headers={"x-csrf-token": owner_csrf},
    )
    assert promoted.status_code == 200

    bob_client, _ = await _client_for(app, "u-bob")
    listing = await bob_client.get("/api/me/notifications")
    assert listing.status_code == 200
    items = listing.json()["notifications"]
    types = {item["type"] for item in items}
    assert {"mention", "role_changed", "muted"} <= types
    mention = next(item for item in items if item["type"] == "mention")
    assert mention["group"]["name"] == "通知群"
    assert mention["payload"]["message_id"] == mentioned.json()["id"]
    assert listing.json()["unread_count"] == 3
    await owner_client.aclose()
    await bob_client.aclose()
