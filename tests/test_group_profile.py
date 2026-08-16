from __future__ import annotations

from typing import Any

import httpx
from starlette.testclient import TestClient

from tests.fixtures.chat import make_friends, seed_session, seed_session_sync

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PDF_BYTES = b"%PDF-1.4\n" + b"\x00" * 8


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def _make_friends(app: Any, pairs: list[tuple[str, str]]) -> None:
    async with app.state.session_factory() as db:
        for a, b in pairs:
            await make_friends(db, a, b)


async def test_announcement_permissions_and_length(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        group = await alice.post(
            "/api/groups",
            json={"name": "公告群", "member_subs": ["u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        group_id = group.json()["id"]
        set_announcement = await alice.patch(
            f"/api/groups/{group_id}/announcement",
            json={"text": "本周六团建"},
            headers={"x-csrf-token": alice_csrf},
        )
        assert set_announcement.status_code == 200
        member_denied = await bob.patch(
            f"/api/groups/{group_id}/announcement",
            json={"text": "篡改"},
            headers={"x-csrf-token": bob_csrf},
        )
        too_long = await alice.patch(
            f"/api/groups/{group_id}/announcement",
            json={"text": "长" * 2001},
            headers={"x-csrf-token": alice_csrf},
        )
        detail = await bob.get(f"/api/groups/{group_id}")
    assert member_denied.status_code == 403
    assert too_long.status_code == 422
    assert detail.json()["announcement"] == "本周六团建"


async def test_group_avatar_rules(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        group = await alice.post(
            "/api/groups",
            json={"name": "头像群", "member_subs": ["u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        group_id = group.json()["id"]
        image = await alice.post(
            "/api/uploads",
            files={"file": ("g.png", PNG_BYTES, "image/png")},
            headers={"x-csrf-token": alice_csrf},
        )
        pdf = await alice.post(
            "/api/uploads",
            files={"file": ("d.pdf", PDF_BYTES, "application/pdf")},
            headers={"x-csrf-token": alice_csrf},
        )
        set_avatar = await alice.post(
            f"/api/groups/{group_id}/avatar",
            json={"url": image.json()["url"]},
            headers={"x-csrf-token": alice_csrf},
        )
        assert set_avatar.status_code == 200
        not_image = await alice.post(
            f"/api/groups/{group_id}/avatar",
            json={"url": pdf.json()["url"]},
            headers={"x-csrf-token": alice_csrf},
        )
        member_denied = await bob.post(
            f"/api/groups/{group_id}/avatar",
            json={"url": "/api/uploads/202608/bob-own.png"},
            headers={"x-csrf-token": bob_csrf},
        )
        summary = await bob.get("/api/conversations")
    assert set_avatar.json()["avatar_url"] == image.json()["url"]
    assert not_image.status_code == 422
    assert member_denied.status_code == 403
    group_item = next(
        conv for conv in summary.json()["conversations"] if conv["group"]
    )
    assert group_item["group"]["avatar_url"] == image.json()["url"]


def test_announcement_ws_broadcast(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")

    async def setup() -> None:
        async with app.state.session_factory() as db:
            await make_friends(db, "u-alice", "u-bob")

    import asyncio

    asyncio.run(setup())
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as bob_ws:
            assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            created = client.post(
                "/api/groups",
                json={"name": "通知", "member_subs": ["u-bob"]},
                headers={"x-csrf-token": alice_csrf},
            )
            group_id = created.json()["id"]
            _receive_type(bob_ws, "group_event")
            updated = client.patch(
                f"/api/groups/{group_id}/announcement",
                json={"text": "新公告"},
                headers={"x-csrf-token": alice_csrf},
            )
            assert updated.status_code == 200
            event = _receive_type(bob_ws, "group_event")
    assert event["event"] == "announcement_updated"


def _receive_type(ws: Any, expected: str) -> dict[str, Any]:
    for _ in range(5):
        event = ws.receive_json()
        if event.get("type") == expected:
            return event
    raise AssertionError(f"expected ws event type {expected!r}")
