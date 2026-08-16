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


async def _group_id(app: Any, client: httpx.AsyncClient, csrf: str) -> int:
    response = await client.post(
        "/api/groups",
        json={"name": "搜索群", "member_subs": ["u-bob"]},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_message_search_within_visible_scope(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-alice", "u-carol"), ("u-bob", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "周末去吃火锅吗"},
            headers={"x-csrf-token": alice_csrf},
        )
        await bob.post(
            "/api/conversations/u-alice/messages",
            json={"content": "火锅太辣，换烧烤"},
            headers={"x-csrf-token": bob_csrf},
        )
        group_id = await _group_id(app, alice, alice_csrf)
        await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "群里也有火锅党"},
            headers={"x-csrf-token": alice_csrf},
        )
        hits = await alice.get("/api/search", params={"kind": "messages", "q": "火锅"})
    body = hits.json()
    assert len(body["messages"]) == 3
    assert all("火锅" in item["snippet"] for item in body["messages"])


async def test_group_messages_not_searchable_by_non_member(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-alice", "u-carol"), ("u-bob", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    carol, _ = await _client_for(app, "u-carol")
    async with alice:
        group_id = await _group_id(app, alice, alice_csrf)
        await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "机密词 hush"},
            headers={"x-csrf-token": alice_csrf},
        )
    async with carol:
        hits = await carol.get("/api/search", params={"kind": "messages", "q": "hush"})
    assert hits.json() == {"messages": [], "next_before": None}


async def test_deleted_messages_excluded_and_pagination(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, csrf = await _client_for(app, "u-alice")
    async with alice:
        for index in range(5):
            await alice.post(
                "/api/conversations/u-bob/messages",
                json={"content": f"目标词 {index}"},
                headers={"x-csrf-token": csrf},
            )
        first = await alice.get(
            "/api/search", params={"kind": "messages", "q": "目标词", "limit": 2}
        )
        page = first.json()
        second = await alice.get(
            "/api/search",
            params={
                "kind": "messages",
                "q": "目标词",
                "limit": 2,
                "before": page["next_before"],
            },
        )
        # 撤回最新的一条，搜索结果应减少
        newest_id = page["messages"][0]["id"]
        removed = await alice.delete(
            f"/api/conversations/u-bob/messages/{newest_id}",
            headers={"x-csrf-token": csrf},
        )
        assert removed.status_code == 200
        after_delete = await alice.get(
            "/api/search", params={"kind": "messages", "q": "目标词"}
        )
    assert len(page["messages"]) == 2
    assert len(second.json()["messages"]) == 2
    assert len(after_delete.json()["messages"]) == 4


async def test_contacts_search_and_validation(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, _ = await _client_for(app, "u-alice")
    async with alice:
        contacts = await alice.get("/api/search", params={"kind": "contacts", "q": "bob"})
        empty_q = await alice.get("/api/search", params={"kind": "contacts", "q": ""})
        bad_limit = await alice.get(
            "/api/search", params={"kind": "messages", "q": "x", "limit": 0}
        )
    assert contacts.status_code == 200
    assert contacts.json()["contacts"][0]["friend_status"] == "friends"
    assert empty_q.status_code == 422
    assert bad_limit.status_code == 422


async def test_search_requires_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/search", params={"kind": "messages", "q": "x"})
    assert response.status_code == 401
