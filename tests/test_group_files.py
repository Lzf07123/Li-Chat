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


async def _upload(client: httpx.AsyncClient, csrf: str, name: str, data: bytes) -> str:
    response = await client.post(
        "/api/uploads",
        files={"file": (name, data, "text/plain")},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return response.json()["url"]


async def test_group_files_aggregates_attachments_with_pagination(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-owner", "u-bob")
    owner_client, owner_csrf = await _client_for(app, "u-owner")
    created = await owner_client.post(
        "/api/groups",
        json={"name": "文件群", "member_subs": ["u-bob"]},
        headers={"x-csrf-token": owner_csrf},
    )
    assert created.status_code == 201
    group_id = created.json()["id"]

    url_one = await _upload(owner_client, owner_csrf, "note1.txt", b"hello one")
    url_two = await _upload(owner_client, owner_csrf, "note2.txt", b"hello two")
    for url in (url_one, url_two):
        sent = await owner_client.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "", "content_type": "file", "attachment": {"url": url}},
            headers={"x-csrf-token": owner_csrf},
        )
        assert sent.status_code == 201

    listing = await owner_client.get(f"/api/groups/{group_id}/files?limit=1")
    assert listing.status_code == 200
    body = listing.json()
    assert len(body["files"]) == 1
    assert body["files"][0]["name"] == "note2.txt"
    assert body["next_before"] is not None
    older = await owner_client.get(
        f"/api/groups/{group_id}/files?limit=1&before={body['next_before']}"
    )
    assert older.status_code == 200
    assert older.json()["files"][0]["name"] == "note1.txt"
    assert older.json()["next_before"] is None
    await owner_client.aclose()


async def test_group_files_only_for_members(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-owner", "u-bob")
        await seed_user(db, "u-stranger", nickname="Stranger")
    owner_client, owner_csrf = await _client_for(app, "u-owner")
    created = await owner_client.post(
        "/api/groups",
        json={"name": "私密文件群", "member_subs": ["u-bob"]},
        headers={"x-csrf-token": owner_csrf},
    )
    group_id = created.json()["id"]
    stranger_client, _ = await _client_for(app, "u-stranger")
    response = await stranger_client.get(f"/api/groups/{group_id}/files")
    assert response.status_code == 404
    await owner_client.aclose()
    await stranger_client.aclose()
