from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select

from app.models import Group, GroupRead, Message, UserConversationSetting
from tests.fixtures.chat import make_friends, seed_session


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def _create_group(
    app: Any, owner: str, members: list[str]
) -> tuple[httpx.AsyncClient, str, int]:
    async with app.state.session_factory() as db:
        for member in members:
            await make_friends(db, owner, member)
    client, csrf = await _client_for(app, owner)
    response = await client.post(
        "/api/groups",
        json={"name": "解散测试群", "member_subs": members},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return client, csrf, response.json()["id"]


async def test_only_owner_can_dissolve_and_cascade_cleanup(app: Any) -> None:
    owner_client, owner_csrf, group_id = await _create_group(
        app, "u-owner", ["u-admin", "u-bob"]
    )
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    admin_client, admin_csrf = await _client_for(app, "u-admin")

    promoted = await owner_client.patch(
        f"/api/groups/{group_id}/members/u-admin",
        json={"role": "admin"},
        headers={"x-csrf-token": owner_csrf},
    )
    assert promoted.status_code == 200

    pinned = await bob_client.patch(
        "/api/conversations/settings",
        json={"kind": "group", "key": str(group_id), "pinned": True},
        headers={"x-csrf-token": bob_csrf},
    )
    assert pinned.status_code == 200
    sent = await bob_client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "before dissolve"},
        headers={"x-csrf-token": bob_csrf},
    )
    assert sent.status_code == 201
    marked = await bob_client.post(
        f"/api/groups/{group_id}/read",
        json={"last_read_id": sent.json()["id"]},
        headers={"x-csrf-token": bob_csrf},
    )
    assert marked.status_code == 200

    by_admin = await admin_client.post(
        f"/api/groups/{group_id}/dissolve", headers={"x-csrf-token": admin_csrf}
    )
    assert by_admin.status_code == 403

    dissolved = await owner_client.post(
        f"/api/groups/{group_id}/dissolve", headers={"x-csrf-token": owner_csrf}
    )
    assert dissolved.status_code == 200
    assert dissolved.json()["status"] == "dissolved"

    detail = await bob_client.get(f"/api/groups/{group_id}")
    assert detail.status_code == 404
    listing = await bob_client.get("/api/groups")
    assert all(item["id"] != group_id for item in listing.json()["groups"])

    async with app.state.session_factory() as db:
        group = await db.get(Group, group_id)
        settings = (
            await db.execute(
                select(UserConversationSetting).where(
                    UserConversationSetting.kind == "group",
                    UserConversationSetting.key == str(group_id),
                )
            )
        ).scalars().all()
        messages = (
            await db.execute(select(Message).where(Message.group_id == group_id))
        ).scalars().all()
        reads = (
            await db.execute(select(GroupRead).where(GroupRead.group_id == group_id))
        ).scalars().all()
    assert group is None
    assert settings == []
    assert messages == []
    assert reads == []

    await owner_client.aclose()
    await bob_client.aclose()
    await admin_client.aclose()
