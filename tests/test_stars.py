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


async def test_star_unstar_idempotent_and_list(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        message = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "值得收藏"},
            headers={"x-csrf-token": alice_csrf},
        )
        message_id = message.json()["id"]
        first = await alice.put(
            f"/api/messages/{message_id}/star", headers={"x-csrf-token": alice_csrf}
        )
        second = await alice.put(
            f"/api/messages/{message_id}/star", headers={"x-csrf-token": alice_csrf}
        )
        stars = await alice.get("/api/me/stars")
        removed = await alice.delete(
            f"/api/messages/{message_id}/star", headers={"x-csrf-token": alice_csrf}
        )
        removed_again = await alice.delete(
            f"/api/messages/{message_id}/star", headers={"x-csrf-token": alice_csrf}
        )
        empty = await alice.get("/api/me/stars")
    assert first.status_code == 200
    assert second.status_code == 200
    assert removed.status_code == 200
    assert removed_again.status_code == 200
    body = stars.json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["id"] == message_id
    assert body["messages"][0]["conversation"]["type"] == "dm"
    assert body["messages"][0]["conversation"]["peer_sub"] == "u-bob"
    assert empty.json() == {"messages": [], "next_before": None}


async def test_star_invisible_message_rejected(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, carol:
        message = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "私下"},
            headers={"x-csrf-token": alice_csrf},
        )
        denied = await carol.put(
            f"/api/messages/{message.json()['id']}/star",
            headers={"x-csrf-token": carol_csrf},
        )
        missing = await carol.put(
            "/api/messages/999999/star", headers={"x-csrf-token": carol_csrf}
        )
    assert denied.status_code == 404
    assert missing.status_code == 404


async def test_history_starred_is_per_viewer(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, _ = await _client_for(app, "u-bob")
    async with alice, bob:
        message = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "标记"},
            headers={"x-csrf-token": alice_csrf},
        )
        message_id = message.json()["id"]
        await alice.put(
            f"/api/messages/{message_id}/star", headers={"x-csrf-token": alice_csrf}
        )
        alice_history = await alice.get("/api/conversations/u-bob/messages")
        bob_history = await bob.get("/api/conversations/u-alice/messages")
    assert alice_history.json()["messages"][0]["starred"] is True
    assert bob_history.json()["messages"][0]["starred"] is False


async def test_star_list_pagination_and_group_ref(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        group = await alice.post(
            "/api/groups",
            json={"name": "收藏群", "member_subs": ["u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        group_id = group.json()["id"]
        for index in range(3):
            message = await alice.post(
                f"/api/groups/{group_id}/messages",
                json={"content": f"m{index}"},
                headers={"x-csrf-token": alice_csrf},
            )
            await alice.put(
                f"/api/messages/{message.json()['id']}/star",
                headers={"x-csrf-token": alice_csrf},
            )
        first = await alice.get("/api/me/stars", params={"limit": 2})
        page = first.json()
        second = await alice.get(
            "/api/me/stars", params={"limit": 2, "cursor": page["next_before"]}
        )
    assert len(page["messages"]) == 2
    assert page["messages"][0]["conversation"]["group_id"] == group_id
    assert len(second.json()["messages"]) == 1


async def test_stars_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/me/stars")
    assert response.status_code == 401
