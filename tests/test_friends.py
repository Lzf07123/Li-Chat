from __future__ import annotations

from typing import Any

import httpx
from starlette.testclient import TestClient

from app.models import Friendship
from tests.fixtures.chat import seed_session, seed_session_sync, seed_user


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
