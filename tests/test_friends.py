from __future__ import annotations

from typing import Any

import httpx

from app.models import Friendship
from tests.fixtures.chat import seed_session, seed_user


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
