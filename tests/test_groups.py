from __future__ import annotations

import asyncio
from typing import Any

import httpx
from starlette.testclient import TestClient

from tests.fixtures.chat import make_friends, seed_session, seed_session_sync


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


async def _create_group(
    client: httpx.AsyncClient,
    csrf: str,
    name: str = "周末群",
    member_subs: list[str] | None = None,
) -> httpx.Response:
    return await client.post(
        "/api/groups",
        json={"name": name, "member_subs": member_subs or []},
        headers={"x-csrf-token": csrf},
    )


async def test_create_group_owner_and_members(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, csrf = await _client_for(app, "u-alice")
    async with alice:
        created = await _create_group(alice, csrf, "老友", ["u-bob", "u-carol"])
        assert created.status_code == 201
        body = created.json()
        assert body["owner_sub"] == "u-alice"
        roles = {member["user"]["sub"]: member["role"] for member in body["members"]}
        assert roles == {
            "u-alice": "owner",
            "u-bob": "member",
            "u-carol": "member",
        }
        mine = await alice.get("/api/groups")
    assert [group["id"] for group in mine.json()["groups"]] == [body["id"]]


async def test_create_group_validation(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    async with app.state.session_factory() as db:
        await make_friends(db, "u-bob", "u-carol")
    alice, csrf = await _client_for(app, "u-alice")
    async with alice:
        blank = await _create_group(alice, csrf, "   ")
        non_friend = await _create_group(alice, csrf, "群", ["u-carol"])
        too_many = await _create_group(
            alice, csrf, "群", [f"ghost-{index}" for index in range(21)]
        )
    assert blank.status_code == 422
    assert non_friend.status_code == 403
    assert too_many.status_code == 422


async def test_role_matrix_and_membership_management(app: Any) -> None:
    await _make_friends(
        app,
        [
            ("u-alice", "u-bob"),
            ("u-alice", "u-carol"),
            ("u-bob", "u-dave"),
            ("u-alice", "u-dave"),
        ],
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, bob, carol:
        created = await _create_group(alice, alice_csrf, "项目", ["u-bob", "u-carol"])
        group_id = created.json()["id"]
        # 成员无权改名/邀请/移除
        member_rename = await bob.patch(
            f"/api/groups/{group_id}", json={"name": "改"}, headers={"x-csrf-token": bob_csrf}
        )
        member_invite = await bob.post(
            f"/api/groups/{group_id}/members",
            json={"member_subs": ["u-dave"]},
            headers={"x-csrf-token": bob_csrf},
        )
        # owner 提拔 bob 为 admin 后具备管理权
        promote = await alice.patch(
            f"/api/groups/{group_id}/members/u-bob",
            json={"role": "admin"},
            headers={"x-csrf-token": alice_csrf},
        )
        assert promote.status_code == 200
        admin_invite = await bob.post(
            f"/api/groups/{group_id}/members",
            json={"member_subs": ["u-dave"]},
            headers={"x-csrf-token": bob_csrf},
        )
        assert admin_invite.status_code == 200
        # admin 不能移除 owner 或其他 admin；owner 可以移除 admin
        admin_remove_owner = await bob.delete(
            f"/api/groups/{group_id}/members/u-alice", headers={"x-csrf-token": bob_csrf}
        )
        promote_carol = await alice.patch(
            f"/api/groups/{group_id}/members/u-carol",
            json={"role": "admin"},
            headers={"x-csrf-token": alice_csrf},
        )
        admin_remove_admin = await bob.delete(
            f"/api/groups/{group_id}/members/u-carol", headers={"x-csrf-token": bob_csrf}
        )
        owner_remove_admin = await alice.delete(
            f"/api/groups/{group_id}/members/u-bob", headers={"x-csrf-token": alice_csrf}
        )
    assert member_rename.status_code == 403
    assert member_invite.status_code == 403
    assert admin_remove_owner.status_code == 403
    assert promote_carol.status_code == 200
    assert admin_remove_admin.status_code == 403
    assert owner_remove_admin.status_code == 200


async def test_leave_and_transfer_rules(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        group_id = (await _create_group(alice, alice_csrf, "家", ["u-bob"])).json()["id"]
        owner_leave = await alice.post(
            f"/api/groups/{group_id}/leave", headers={"x-csrf-token": alice_csrf}
        )
        member_transfer = await bob.post(
            f"/api/groups/{group_id}/transfer",
            json={"new_owner_sub": "u-bob"},
            headers={"x-csrf-token": bob_csrf},
        )
        transfer = await alice.post(
            f"/api/groups/{group_id}/transfer",
            json={"new_owner_sub": "u-bob"},
            headers={"x-csrf-token": alice_csrf},
        )
        assert transfer.status_code == 200
        old_owner_leave = await alice.post(
            f"/api/groups/{group_id}/leave", headers={"x-csrf-token": alice_csrf}
        )
        assert old_owner_leave.status_code == 200
        detail = await bob.get(f"/api/groups/{group_id}")
    assert owner_leave.status_code == 409
    assert member_transfer.status_code == 403
    assert detail.json()["owner_sub"] == "u-bob"


async def test_non_member_cannot_see_group(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-bob", "u-carol")])
    alice, csrf = await _client_for(app, "u-alice")
    carol, _ = await _client_for(app, "u-carol")
    async with alice:
        group_id = (await _create_group(alice, csrf, "私密", ["u-bob"])).json()["id"]
    async with carol:
        detail = await carol.get(f"/api/groups/{group_id}")
        mine = await carol.get("/api/groups")
    assert detail.status_code == 404
    assert mine.json() == {"groups": []}


def test_group_events_pushed_to_members_over_ws(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")

    async def run_friends() -> None:
        await _make_friends(app, [("u-alice", "u-bob")])

    asyncio.run(run_friends())
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
            assert created.status_code == 201
            event = bob_ws.receive_json()
    assert event["type"] == "group_event"
    assert event["event"] == "created"
    assert event["group"]["name"] == "通知"
