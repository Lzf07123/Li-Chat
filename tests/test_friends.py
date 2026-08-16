from __future__ import annotations

import asyncio
from typing import Any

import httpx
from starlette.testclient import TestClient

from app.models import Friendship
from tests.fixtures.chat import make_friends, seed_session, seed_session_sync, seed_user


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def test_search_matches_nickname_or_email_without_leaking_email(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-me", nickname="Me", email="me@example.com")
        await seed_user(db, "u-alice", nickname="Alice", email="alice@example.com")
        await seed_user(db, "u-bob", nickname="Bob", email="bob@example.com")
    client, _ = await _client_for(app, "u-me")
    async with client:
        response = await client.get("/api/users/search", params={"q": "alice"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert [item["sub"] for item in results] == ["u-alice"]
    assert "email" not in results[0]

    client, _ = await _client_for(app, "u-me")
    async with client:
        response = await client.get("/api/users/search", params={"q": "bob@"})
    assert response.status_code == 200
    assert [item["sub"] for item in response.json()["results"]] == ["u-bob"]


async def test_search_reports_friend_status(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-me", nickname="u-me")
        await seed_user(db, "u-friend", nickname="u-friend")
        await seed_user(db, "u-in", nickname="u-in")
        await seed_user(db, "u-out", nickname="u-out")
        db.add_all(
            [
                Friendship(requester_sub="u-me", addressee_sub="u-friend", status="accepted"),
                Friendship(requester_sub="u-in", addressee_sub="u-me", status="pending"),
                Friendship(requester_sub="u-me", addressee_sub="u-out", status="pending"),
            ]
        )
        await db.commit()
    client, _ = await _client_for(app, "u-me")
    async with client:
        response = await client.get("/api/users/search", params={"q": "u-"})
    assert response.status_code == 200
    status_by_sub = {item["sub"]: item["friend_status"] for item in response.json()["results"]}
    assert status_by_sub["u-friend"] == "friends"
    assert status_by_sub["u-in"] == "incoming"
    assert status_by_sub["u-out"] == "outgoing"


async def test_search_rejects_blank_or_long_query(app: Any) -> None:
    client, _ = await _client_for(app, "u-me")
    async with client:
        blank = await client.get("/api/users/search", params={"q": ""})
        too_long = await client.get("/api/users/search", params={"q": "x" * 65})
    assert blank.status_code == 422
    assert too_long.status_code == 422


async def test_search_requires_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/users/search", params={"q": "x"})
    assert response.status_code == 401


async def test_set_and_clear_friend_remark(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-me", "u-bob")
    client, csrf = await _client_for(app, "u-me")
    async with client:
        set_remark = await client.patch(
            "/api/friends/u-bob/remark",
            json={"remark": "老王"},
            headers={"x-csrf-token": csrf},
        )
        listed = await client.get("/api/friends")
        clear_remark = await client.patch(
            "/api/friends/u-bob/remark",
            json={"remark": ""},
            headers={"x-csrf-token": csrf},
        )
        relisted = await client.get("/api/friends")
    assert set_remark.status_code == 200
    assert set_remark.json() == {"remark": "老王"}
    friends = {item["sub"]: item for item in listed.json()["friends"]}
    assert friends["u-bob"]["remark"] == "老王"
    assert clear_remark.status_code == 200
    friends_after = {item["sub"]: item for item in relisted.json()["friends"]}
    assert friends_after["u-bob"]["remark"] is None


async def test_remark_requires_friendship_and_length(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-me", "u-bob")
        await seed_user(db, "u-stranger", nickname="Stranger")
    client, csrf = await _client_for(app, "u-me")
    async with client:
        not_friend = await client.patch(
            "/api/friends/u-stranger/remark",
            json={"remark": "X"},
            headers={"x-csrf-token": csrf},
        )
        too_long = await client.patch(
            "/api/friends/u-bob/remark",
            json={"remark": "长" * 33},
            headers={"x-csrf-token": csrf},
        )
    assert not_friend.status_code == 404
    assert too_long.status_code == 422


async def test_send_request_ok(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-bob"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["requester_sub"] == "u-alice"
    assert body["addressee_sub"] == "u-bob"
    assert body["status"] == "pending"
    assert body["created_at"].endswith("Z")


async def test_send_request_to_self_rejected(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-alice"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 400


async def test_send_request_unknown_user_404(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-ghost"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 404


async def test_send_request_conflicts_409(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
        await seed_user(db, "u-carol", nickname="Carol")
        db.add_all(
            [
                Friendship(requester_sub="u-alice", addressee_sub="u-bob", status="pending"),
                Friendship(requester_sub="u-carol", addressee_sub="u-alice", status="pending"),
            ]
        )
        await db.commit()
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        resend = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-bob"},
            headers={"x-csrf-token": csrf},
        )
        incoming = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-carol"},
            headers={"x-csrf-token": csrf},
        )
    assert resend.status_code == 409
    assert incoming.status_code == 409


async def test_requests_list_shapes(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
        await seed_user(db, "u-carol", nickname="Carol")
        db.add_all(
            [
                Friendship(requester_sub="u-alice", addressee_sub="u-bob", status="pending"),
                Friendship(requester_sub="u-carol", addressee_sub="u-alice", status="pending"),
            ]
        )
        await db.commit()
    client, _ = await _client_for(app, "u-alice")
    async with client:
        response = await client.get("/api/friends/requests")
    assert response.status_code == 200
    body = response.json()
    assert [item["requester"]["sub"] for item in body["incoming"]] == ["u-carol"]
    assert [item["addressee"]["sub"] for item in body["outgoing"]] == ["u-bob"]
    assert body["incoming"][0]["created_at"].endswith("Z")


async def test_send_request_requires_csrf(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
    client, _ = await _client_for(app, "u-alice")
    async with client:
        response = await client.post("/api/friends/requests", json={"to_sub": "u-bob"})
    assert response.status_code == 403


def test_request_received_pushed_over_ws(app: Any) -> None:
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            response = client.post(
                "/api/friends/requests",
                json={"to_sub": "u-bob"},
                headers={"x-csrf-token": alice_csrf},
            )
            assert response.status_code == 201
            event = ws.receive_json()
    assert event["type"] == "friend_event"
    assert event["event"] == "request_received"
    assert event["by_sub"] == "u-alice"
    assert event["at"].endswith("Z")


async def _seed_pending(app: Any, requester: str, addressee: str) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, requester, nickname=requester)
        await seed_user(db, addressee, nickname=addressee)
        db.add(Friendship(requester_sub=requester, addressee_sub=addressee, status="pending"))
        await db.commit()


async def test_accept_request_ok(app: Any) -> None:
    await _seed_pending(app, "u-bob", "u-alice")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/accept",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    client, _ = await _client_for(app, "u-alice")
    async with client:
        friends = await client.get("/api/friends")
    assert [item["sub"] for item in friends.json()["friends"]] == ["u-bob"]


async def test_accept_reject_only_addressee(app: Any) -> None:
    await _seed_pending(app, "u-bob", "u-alice")
    client, csrf = await _client_for(app, "u-bob")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/accept",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 404
    client, csrf = await _client_for(app, "u-bob")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/reject",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 404


async def test_reject_request_removes_pending(app: Any) -> None:
    await _seed_pending(app, "u-bob", "u-alice")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/reject",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "rejected"}
    client, _ = await _client_for(app, "u-alice")
    async with client:
        requests = await client.get("/api/friends/requests")
    assert requests.json() == {"incoming": [], "outgoing": []}


async def test_remove_friend_and_missing(app: Any) -> None:
    async with app.state.session_factory() as db:
        from tests.fixtures.chat import make_friends

        await make_friends(db, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        removed = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
        missing = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
    assert removed.status_code == 200
    assert removed.json() == {"status": "removed"}
    assert missing.status_code == 404


async def test_remove_requires_csrf(app: Any) -> None:
    client, _ = await _client_for(app, "u-alice")
    async with client:
        response = await client.delete("/api/friends/u-bob")
    assert response.status_code == 403


async def test_remove_outgoing_request_cancels(app: Any) -> None:
    await _seed_pending(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        removed = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
        requests = await client.get("/api/friends/requests")
    assert removed.status_code == 200
    assert requests.json() == {"incoming": [], "outgoing": []}


def _seed_pending_sync(app: Any, requester: str, addressee: str) -> None:
    def run() -> None:
        async def inner() -> None:
            async with app.state.session_factory() as db:
                await seed_user(db, requester, nickname=requester)
                await seed_user(db, addressee, nickname=addressee)
                db.add(
                    Friendship(
                        requester_sub=requester,
                        addressee_sub=addressee,
                        status="pending",
                    )
                )
                await db.commit()

        asyncio.run(inner())

    run()


def test_accepted_and_removed_pushed_over_ws(app: Any) -> None:
    _seed_pending_sync(app, "u-bob", "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            response = client.post(
                "/api/friends/requests/u-bob/accept",
                headers={"x-csrf-token": alice_csrf},
            )
            assert response.status_code == 200
            accepted = ws.receive_json()
            removed = client.delete(
                "/api/friends/u-bob", headers={"x-csrf-token": alice_csrf}
            )
            assert removed.status_code == 200
            friend_removed = ws.receive_json()
    assert accepted["event"] == "request_accepted"
    assert accepted["by_sub"] == "u-alice"
    assert friend_removed["event"] == "friend_removed"
    assert friend_removed["by_sub"] == "u-alice"


def test_reject_pushed_over_ws(app: Any) -> None:
    _seed_pending_sync(app, "u-bob", "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            response = client.post(
                "/api/friends/requests/u-bob/reject",
                headers={"x-csrf-token": alice_csrf},
            )
            assert response.status_code == 200
            rejected = ws.receive_json()
    assert rejected["event"] == "request_rejected"
    assert rejected["by_sub"] == "u-alice"


async def test_recommendations_exclude_self_friends_and_pending(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-me", nickname="u-me")
        await seed_user(db, "u-friend", nickname="u-friend")
        await seed_user(db, "u-in", nickname="u-in")
        await seed_user(db, "u-out", nickname="u-out")
        await seed_user(db, "u-a", nickname="u-a")
        await seed_user(db, "u-b", nickname="u-b")
        await seed_user(db, "u-c", nickname="u-c")
        db.add_all(
            [
                Friendship(requester_sub="u-me", addressee_sub="u-friend", status="accepted"),
                Friendship(requester_sub="u-in", addressee_sub="u-me", status="pending"),
                Friendship(requester_sub="u-me", addressee_sub="u-out", status="pending"),
            ]
        )
        await db.commit()
    client, _ = await _client_for(app, "u-me")
    async with client:
        response = await client.get("/api/friends/recommendations")
    assert response.status_code == 200
    subs = {item["sub"] for item in response.json()["friends"]}
    assert subs == {"u-a", "u-b", "u-c"}
    assert all("email" not in item for item in response.json()["friends"])


async def test_recommendations_limit_and_validation(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-me", nickname="u-me")
        for index in range(5):
            await seed_user(db, f"u-{index}", nickname=f"u-{index}")
    client, _ = await _client_for(app, "u-me")
    async with client:
        limited = await client.get("/api/friends/recommendations", params={"limit": 2})
        too_small = await client.get("/api/friends/recommendations", params={"limit": 0})
        too_large = await client.get("/api/friends/recommendations", params={"limit": 21})
    assert limited.status_code == 200
    assert len(limited.json()["friends"]) == 2
    assert too_small.status_code == 422
    assert too_large.status_code == 422


async def test_recommendations_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/friends/recommendations")
    assert response.status_code == 401
