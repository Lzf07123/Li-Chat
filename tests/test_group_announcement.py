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


async def test_announcement_updated_at_tracked(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-owner", "u-bob")
    client, csrf = await _client_for(app, "u-owner")
    created = await client.post(
        "/api/groups",
        json={"name": "公告群", "member_subs": ["u-bob"]},
        headers={"x-csrf-token": csrf},
    )
    group_id = created.json()["id"]
    assert created.json()["announcement_updated_at"] is None
    updated = await client.patch(
        f"/api/groups/{group_id}/announcement",
        json={"text": "第一条公告"},
        headers={"x-csrf-token": csrf},
    )
    assert updated.status_code == 200
    first = updated.json()["announcement_updated_at"]
    assert first is not None
    cleared = await client.patch(
        f"/api/groups/{group_id}/announcement",
        json={"text": ""},
        headers={"x-csrf-token": csrf},
    )
    assert cleared.status_code == 200
    assert cleared.json()["announcement"] == ""
    assert cleared.json()["announcement_updated_at"] is not None
    await client.aclose()
