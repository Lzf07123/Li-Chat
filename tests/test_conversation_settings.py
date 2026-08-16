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


async def _make_friends(app: Any, pairs: list[tuple[str, str]]) -> None:
    async with app.state.session_factory() as db:
        for a, b in pairs:
            await make_friends(db, a, b)


async def _patch(
    client: httpx.AsyncClient,
    csrf: str,
    kind: str,
    key: str,
    *,
    pinned: bool | None = None,
    muted: bool | None = None,
) -> httpx.Response:
    body: dict[str, Any] = {"kind": kind, "key": key}
    if pinned is not None:
        body["pinned"] = pinned
    if muted is not None:
        body["muted"] = muted
    return await client.patch(
        "/api/conversations/settings",
        json=body,
        headers={"x-csrf-token": csrf},
    )


async def test_pin_mute_upsert_and_reflect(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        await bob.post(
            "/api/conversations/u-alice/messages",
            json={"content": "你好"},
            headers={"x-csrf-token": bob_csrf},
        )
        key = ":".join(sorted(["u-alice", "u-bob"]))
        pin = await _patch(alice, alice_csrf, "dm", key, pinned=True)
        mute = await _patch(alice, alice_csrf, "dm", key, muted=True)
        assert pin.status_code == 200
        assert mute.status_code == 200
        summary = await alice.get("/api/conversations")
    item = summary.json()["conversations"][0]
    assert item["pinned"] is True
    assert item["muted"] is True


async def test_pinned_conversation_sorted_first(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, carol:
        await carol.post(
            "/api/conversations/u-alice/messages",
            json={"content": "新的会话"},
            headers={"x-csrf-token": carol_csrf},
        )
        carol_key = ":".join(sorted(["u-alice", "u-carol"]))
        await _patch(alice, alice_csrf, "dm", carol_key, pinned=True)
        summary = await alice.get("/api/conversations")
    items = summary.json()["conversations"]
    assert items[0]["peer"]["sub"] == "u-carol"
    assert items[0]["pinned"] is True
    assert items[1]["peer"]["sub"] == "u-bob"


async def test_setting_key_ownership_validation(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        group = await alice.post(
            "/api/groups",
            json={"name": "群", "member_subs": ["u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        group_id = group.json()["id"]
        foreign_dm = await _patch(
            alice, alice_csrf, "dm", ":".join(sorted(["u-bob", "u-carol"])), pinned=True
        )
        bad_group = await _patch(
            alice, alice_csrf, "group", str(group_id + 999), pinned=True
        )
        good_group = await _patch(
            alice, alice_csrf, "group", str(group_id), pinned=True
        )
        bad_kind = await _patch(alice, alice_csrf, "weird", "x", pinned=True)
        nothing = await _patch(alice, alice_csrf, "dm", "u-alice:u-bob")
    assert foreign_dm.status_code == 404
    assert bad_group.status_code == 404
    assert good_group.status_code == 200
    assert bad_kind.status_code == 422
    assert nothing.status_code == 422


async def test_settings_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.patch(
        "/api/conversations/settings",
        json={"kind": "dm", "key": "a:b", "pinned": True},
    )
    assert response.status_code == 401
