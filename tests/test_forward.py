from __future__ import annotations

from typing import Any

import httpx

from tests.fixtures.chat import make_friends, seed_session

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


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


async def test_forward_dm_message_to_another_friend(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-bob", "u-carol"), ("u-alice", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, _ = await _client_for(app, "u-carol")
    async with alice, bob, carol:
        original = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "转发我"},
            headers={"x-csrf-token": alice_csrf},
        )
        forwarded = await bob.post(
            "/api/conversations/u-carol/forward",
            json={"message_id": original.json()["id"]},
            headers={"x-csrf-token": bob_csrf},
        )
        assert forwarded.status_code == 201
        body = forwarded.json()
        carol_history = await carol.get("/api/conversations/u-bob/messages")
    assert body["forwarded"] is True
    assert body["content"] == "转发我"
    assert body["sender_sub"] == "u-bob"
    assert carol_history.json()["messages"][0]["forwarded"] is True


async def test_forward_between_group_and_dm(app: Any) -> None:
    await _make_friends(app, [("u-alice", "u-bob"), ("u-alice", "u-carol")])
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        group = await alice.post(
            "/api/groups",
            json={"name": "群", "member_subs": ["u-bob"]},
            headers={"x-csrf-token": alice_csrf},
        )
        group_id = group.json()["id"]
        group_message = await alice.post(
            f"/api/groups/{group_id}/messages",
            json={"content": "群内消息"},
            headers={"x-csrf-token": alice_csrf},
        )
        to_dm = await bob.post(
            "/api/conversations/u-alice/forward",
            json={"message_id": group_message.json()["id"]},
            headers={"x-csrf-token": bob_csrf},
        )
        assert to_dm.status_code == 201
        dm_message = await bob.post(
            "/api/conversations/u-alice/messages",
            json={"content": "DM 消息"},
            headers={"x-csrf-token": bob_csrf},
        )
        to_group = await bob.post(
            f"/api/groups/{group_id}/forward",
            json={"message_id": dm_message.json()["id"]},
            headers={"x-csrf-token": bob_csrf},
        )
    assert to_dm.json()["forwarded"] is True
    assert to_group.status_code == 201
    assert to_group.json()["group_id"] == group_id


async def test_forward_permissions_and_deleted(app: Any) -> None:
    await _make_friends(
        app, [("u-alice", "u-bob"), ("u-alice", "u-carol"), ("u-bob", "u-carol")]
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, bob, carol:
        message = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "私密"},
            headers={"x-csrf-token": alice_csrf},
        )
        message_id = message.json()["id"]
        # carol 不是该会话参与者，不能转发
        invisible = await carol.post(
            "/api/conversations/u-alice/forward",
            json={"message_id": message_id},
            headers={"x-csrf-token": carol_csrf},
        )
        removed = await alice.delete(
            f"/api/conversations/u-bob/messages/{message_id}",
            headers={"x-csrf-token": alice_csrf},
        )
        assert removed.status_code == 200
        deleted = await bob.post(
            "/api/conversations/u-carol/forward",
            json={"message_id": message_id},
            headers={"x-csrf-token": bob_csrf},
        )
        missing = await bob.post(
            "/api/conversations/u-carol/forward",
            json={"message_id": 999999},
            headers={"x-csrf-token": bob_csrf},
        )
    assert invisible.status_code == 404
    assert deleted.status_code == 409
    assert missing.status_code == 404


async def test_forward_attachment_recipient_can_download(app: Any) -> None:
    await _make_friends(
        app,
        [
            ("u-alice", "u-bob"),
            ("u-bob", "u-carol"),
            ("u-alice", "u-carol"),
            ("u-alice", "u-dave"),
        ],
    )
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    carol, _ = await _client_for(app, "u-carol")
    dave, _ = await _client_for(app, "u-dave")
    async with alice, bob, carol:
        uploaded = await alice.post(
            "/api/uploads",
            files={"file": ("pic.png", PNG_BYTES, "image/png")},
            headers={"x-csrf-token": alice_csrf},
        )
        url = uploaded.json()["url"]
        message = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "", "content_type": "image", "attachment": {"url": url}},
            headers={"x-csrf-token": alice_csrf},
        )
        forwarded = await bob.post(
            "/api/conversations/u-carol/forward",
            json={"message_id": message.json()["id"]},
            headers={"x-csrf-token": bob_csrf},
        )
        assert forwarded.status_code == 201
        # 转发后 carol 成为引用该附件的会话参与者，可回源
        carol_download = await carol.get(url)
    async with dave:
        stranger_download = await dave.get(url)
    assert carol_download.status_code == 200
    assert carol_download.content == PNG_BYTES
    assert stranger_download.status_code == 403
