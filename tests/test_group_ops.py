from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx

from app.models import Message
from app.timeutil import utcnow
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


async def _group(app: Any, client: httpx.AsyncClient, csrf: str) -> int:
    response = await client.post(
        "/api/groups",
        json={"name": "操作群", "member_subs": ["u-bob"]},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_group_edit_and_delete_permissions(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-alice", "u-carol"), ("u-bob", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, bob, carol:
        group_id = await _group(app, alice, alice_csrf)
        sent = await bob.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "原文"},
            headers={"x-csrf-token": bob_csrf},
        )
        message_id = sent.json()["id"]
        edited = await bob.patch(
            f"/api/groups/{group_id}/messages/{message_id}",
            json={"content": "改过"},
            headers={"x-csrf-token": bob_csrf},
        )
        assert edited.status_code == 200
        not_sender = await alice.patch(
            f"/api/groups/{group_id}/messages/{message_id}",
            json={"content": "越权"},
            headers={"x-csrf-token": alice_csrf},
        )
        outsider = await carol.patch(
            f"/api/groups/{group_id}/messages/{message_id}",
            json={"content": "外人"},
            headers={"x-csrf-token": carol_csrf},
        )
        removed = await bob.delete(
            f"/api/groups/{group_id}/messages/{message_id}",
            headers={"x-csrf-token": bob_csrf},
        )
        assert removed.status_code == 200
        edit_after = await bob.patch(
            f"/api/groups/{group_id}/messages/{message_id}",
            json={"content": "再改"},
            headers={"x-csrf-token": bob_csrf},
        )
        history = await alice.get(f"/api/groups/{group_id}/messages")
    assert edited.json()["content"] == "改过"
    assert not_sender.status_code == 403
    assert outsider.status_code == 404
    assert edit_after.status_code == 409
    assert history.json()["messages"][0]["deleted"] is True
    assert history.json()["messages"][0]["content"] is None


async def test_group_edit_window_expiry(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        group_id = await _group(app, alice, alice_csrf)
        sent = await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "过期"},
            headers={"x-csrf-token": alice_csrf},
        )
        message_id = sent.json()["id"]
        async with app.state.session_factory() as db:
            message = await db.get(Message, message_id)
            assert message is not None
            message.created_at = utcnow() - timedelta(minutes=6)
            await db.commit()
        expired = await alice.patch(
            f"/api/groups/{group_id}/messages/{message_id}",
            json={"content": "超时"},
            headers={"x-csrf-token": alice_csrf},
        )
    assert expired.status_code == 409


async def test_group_reactions(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-alice", "u-carol"), ("u-bob", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, bob, carol:
        group_id = await _group(app, alice, alice_csrf)
        sent = await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "点赞"},
            headers={"x-csrf-token": alice_csrf},
        )
        message_id = sent.json()["id"]
        added = await bob.put(
            f"/api/groups/{group_id}/messages/{message_id}/reactions",
            json={"emoji": "👍"},
            headers={"x-csrf-token": bob_csrf},
        )
        outsider = await carol.put(
            f"/api/groups/{group_id}/messages/{message_id}/reactions",
            json={"emoji": "👍"},
            headers={"x-csrf-token": carol_csrf},
        )
        removed = await bob.delete(
            f"/api/groups/{group_id}/messages/{message_id}/reactions?emoji=👍",
            headers={"x-csrf-token": bob_csrf},
        )
        history = await alice.get(f"/api/groups/{group_id}/messages")
    assert added.status_code == 200
    assert added.json()["count"] == 1
    assert outsider.status_code == 404
    assert removed.status_code == 200
    assert removed.json()["count"] == 0
    assert history.json()["messages"][0]["reactions"] == []
