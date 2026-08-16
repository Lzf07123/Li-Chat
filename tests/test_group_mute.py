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


async def _create_group(
    app: Any, owner: str, members: list[str]
) -> tuple[httpx.AsyncClient, str, int]:
    async with app.state.session_factory() as db:
        for member in members:
            await make_friends(db, owner, member)
    client, csrf = await _client_for(app, owner)
    response = await client.post(
        "/api/groups",
        json={"name": "测试群", "member_subs": members},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return client, csrf, response.json()["id"]


async def test_owner_mute_blocks_group_message(app: Any) -> None:
    owner_client, owner_csrf, group_id = await _create_group(app, "u-owner", ["u-bob"])
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    muted = await owner_client.patch(
        f"/api/groups/{group_id}/members/u-bob/mute",
        json={"muted": True},
        headers={"x-csrf-token": owner_csrf},
    )
    blocked = await bob_client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "hello"},
        headers={"x-csrf-token": bob_csrf},
    )
    unmuted = await owner_client.patch(
        f"/api/groups/{group_id}/members/u-bob/mute",
        json={"muted": False},
        headers={"x-csrf-token": owner_csrf},
    )
    allowed = await bob_client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": "hello again"},
        headers={"x-csrf-token": bob_csrf},
    )
    assert muted.status_code == 200
    assert muted.json()["status"] == "muted"
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "you are muted"
    assert unmuted.status_code == 200
    assert allowed.status_code == 201
    await owner_client.aclose()
    await bob_client.aclose()


async def test_mute_permission_matrix(app: Any) -> None:
    owner_client, owner_csrf, group_id = await _create_group(
        app, "u-owner", ["u-admin", "u-bob"]
    )
    bob_client, bob_csrf = await _client_for(app, "u-bob")
    admin_client, admin_csrf = await _client_for(app, "u-admin")
    promote = await owner_client.patch(
        f"/api/groups/{group_id}/members/u-admin",
        json={"role": "admin"},
        headers={"x-csrf-token": owner_csrf},
    )
    by_member = await bob_client.patch(
        f"/api/groups/{group_id}/members/u-admin/mute",
        json={"muted": True},
        headers={"x-csrf-token": bob_csrf},
    )
    admin_mutes_owner = await admin_client.patch(
        f"/api/groups/{group_id}/members/u-owner/mute",
        json={"muted": True},
        headers={"x-csrf-token": admin_csrf},
    )
    admin_mutes_self = await admin_client.patch(
        f"/api/groups/{group_id}/members/u-admin/mute",
        json={"muted": True},
        headers={"x-csrf-token": admin_csrf},
    )
    owner_mutes_admin = await owner_client.patch(
        f"/api/groups/{group_id}/members/u-admin/mute",
        json={"muted": True},
        headers={"x-csrf-token": owner_csrf},
    )
    assert promote.status_code == 200
    assert by_member.status_code == 403
    assert admin_mutes_owner.status_code == 403
    assert admin_mutes_self.status_code == 400
    assert owner_mutes_admin.status_code == 403
    await owner_client.aclose()
    await bob_client.aclose()
    await admin_client.aclose()
