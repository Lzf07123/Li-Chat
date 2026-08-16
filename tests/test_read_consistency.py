from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select

from app.models import DmRead, GroupRead, UserConversationSetting
from tests.fixtures.chat import make_friends, seed_session


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def test_dm_read_cursor_only_advances(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-alice", "u-bob")
    alice_client, alice_csrf = await _client_for(app, "u-alice")
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    for text in ("one", "two"):
        sent = await alice_client.post(
            "/api/conversations/u-bob/messages",
            json={"content": text},
            headers={"x-csrf-token": alice_csrf},
        )
        assert sent.status_code == 201
    marked = await bob_client.post(
        "/api/conversations/u-alice/read",
        json={"last_read_id": 2},
        headers={"x-csrf-token": bob_csrf},
    )
    assert marked.status_code == 200
    rollback = await bob_client.post(
        "/api/conversations/u-alice/read",
        json={"last_read_id": 1},
        headers={"x-csrf-token": bob_csrf},
    )
    assert rollback.status_code == 200
    async with app.state.session_factory() as db:
        row = await db.get(DmRead, ("u-bob", "u-alice", "u-bob"))
    assert row is not None
    assert row.last_read_message_id == 2
    await alice_client.aclose()
    await bob_client.aclose()


async def test_leave_and_remove_clean_group_reads(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-owner", "u-bob")
        await make_friends(db, "u-owner", "u-carol")
    owner_client, owner_csrf = await _client_for(app, "u-owner")
    created = await owner_client.post(
        "/api/groups",
        json={"name": "一致性群", "member_subs": ["u-bob", "u-carol"]},
        headers={"x-csrf-token": owner_csrf},
    )
    group_id = created.json()["id"]
    sent = await owner_client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "read this"},
        headers={"x-csrf-token": owner_csrf},
    )
    message_id = sent.json()["id"]
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    await bob_client.post(
        f"/api/groups/{group_id}/read",
        json={"last_read_id": message_id},
        headers={"x-csrf-token": bob_csrf},
    )
    await bob_client.post(
        "/api/conversations/settings",
        json={"kind": "group", "key": str(group_id), "pinned": True},
        headers={"x-csrf-token": bob_csrf},
    )
    left = await bob_client.post(
        f"/api/groups/{group_id}/leave", headers={"x-csrf-token": bob_csrf}
    )
    assert left.status_code == 200
    async with app.state.session_factory() as db:
        read_row = await db.get(GroupRead, ("u-bob", group_id))
        settings = (
            await db.execute(
                select(UserConversationSetting).where(
                    UserConversationSetting.user_sub == "u-bob",
                    UserConversationSetting.kind == "group",
                    UserConversationSetting.key == str(group_id),
                )
            )
        ).scalars().all()
    assert read_row is None
    assert settings == []

    carol_client, carol_csrf = await _client_for(app, "u-carol")
    await carol_client.post(
        f"/api/groups/{group_id}/read",
        json={"last_read_id": message_id},
        headers={"x-csrf-token": carol_csrf},
    )
    removed = await owner_client.delete(
        f"/api/groups/{group_id}/members/u-carol",
        headers={"x-csrf-token": owner_csrf},
    )
    assert removed.status_code == 200
    async with app.state.session_factory() as db:
        carol_read = await db.get(GroupRead, ("u-carol", group_id))
    assert carol_read is None
    await owner_client.aclose()
    await bob_client.aclose()
    await carol_client.aclose()
