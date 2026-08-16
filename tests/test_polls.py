from __future__ import annotations

from typing import Any

import httpx

from tests.fixtures.chat import make_friends, seed_session, seed_user


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def _create_group(
    app: Any, owner: str, members: list[str]
) -> tuple[httpx.AsyncClient, str, int]:
    async with app.state.session_factory() as db:
        for member in members:
            await make_friends(db, owner, member)
    client, csrf = await _client_for(app, owner)
    response = await client.post(
        "/api/groups",
        json={"name": "投票群", "member_subs": members},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return client, csrf, response.json()["id"]


async def _create_poll(client: httpx.AsyncClient, csrf: str, group_id: int) -> dict[str, Any]:
    response = await client.post(
        f"/api/groups/{group_id}/messages",
        json={
            "content": "",
            "content_type": "poll",
            "poll": {"question": "周末去哪？", "options": ["爬山", "海边", "宅家"]},
        },
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["content_type"] == "poll"
    assert body["poll"]["question"] == "周末去哪？"
    return body["poll"]


async def test_poll_create_vote_change_and_close(app: Any) -> None:
    owner_client, owner_csrf, group_id = await _create_group(app, "u-owner", ["u-bob"])
    poll = await _create_poll(owner_client, owner_csrf, group_id)
    poll_id = poll["id"]
    assert poll["closed"] is False
    assert [item["count"] for item in poll["options"]] == [0, 0, 0]

    bob_client, bob_csrf = await _client_for(app, "u-bob")
    voted = await bob_client.put(
        f"/api/groups/{group_id}/polls/{poll_id}/vote",
        json={"option_indexes": [0]},
        headers={"x-csrf-token": bob_csrf},
    )
    assert voted.status_code == 200
    assert voted.json()["my_votes"] == [0]
    assert voted.json()["options"][0]["count"] == 1
    assert voted.json()["total_votes"] == 1

    changed = await bob_client.put(
        f"/api/groups/{group_id}/polls/{poll_id}/vote",
        json={"option_indexes": [1]},
        headers={"x-csrf-token": bob_csrf},
    )
    assert changed.status_code == 200
    assert changed.json()["my_votes"] == [1]
    assert changed.json()["options"][0]["count"] == 0
    assert changed.json()["options"][1]["count"] == 1

    closed = await owner_client.post(
        f"/api/groups/{group_id}/polls/{poll_id}/close",
        headers={"x-csrf-token": owner_csrf},
    )
    assert closed.status_code == 200
    assert closed.json()["closed"] is True

    late_vote = await bob_client.put(
        f"/api/groups/{group_id}/polls/{poll_id}/vote",
        json={"option_indexes": [2]},
        headers={"x-csrf-token": bob_csrf},
    )
    assert late_vote.status_code == 409
    await owner_client.aclose()
    await bob_client.aclose()


async def test_poll_permissions_and_validation(app: Any) -> None:
    owner_client, owner_csrf, group_id = await _create_group(app, "u-owner", ["u-bob"])
    poll = await _create_poll(owner_client, owner_csrf, group_id)
    poll_id = poll["id"]
    bob_client, bob_csrf = await _client_for(app, "u-bob")

    invalid = await bob_client.put(
        f"/api/groups/{group_id}/polls/{poll_id}/vote",
        json={"option_indexes": [9]},
        headers={"x-csrf-token": bob_csrf},
    )
    assert invalid.status_code == 422

    multi = await bob_client.put(
        f"/api/groups/{group_id}/polls/{poll_id}/vote",
        json={"option_indexes": [0, 1]},
        headers={"x-csrf-token": bob_csrf},
    )
    assert multi.status_code == 422

    closed_by_member = await bob_client.post(
        f"/api/groups/{group_id}/polls/{poll_id}/close",
        headers={"x-csrf-token": bob_csrf},
    )
    assert closed_by_member.status_code == 403

    async with app.state.session_factory() as db:
        await seed_user(db, "u-stranger", nickname="Stranger")
    stranger_client, stranger_csrf = await _client_for(app, "u-stranger")
    outside_vote = await stranger_client.put(
        f"/api/groups/{group_id}/polls/{poll_id}/vote",
        json={"option_indexes": [0]},
        headers={"x-csrf-token": stranger_csrf},
    )
    assert outside_vote.status_code == 404
    await owner_client.aclose()
    await bob_client.aclose()
    await stranger_client.aclose()


async def test_multiple_choice_poll_and_forward_rejected(app: Any) -> None:
    owner_client, owner_csrf, group_id = await _create_group(app, "u-owner", ["u-bob"])
    created = await owner_client.post(
        f"/api/groups/{group_id}/messages",
        json={
            "content": "",
            "content_type": "poll",
            "poll": {
                "question": "爱吃啥？",
                "options": ["火锅", "烧烤", "日料"],
                "multiple": True,
            },
        },
        headers={"x-csrf-token": owner_csrf},
    )
    assert created.status_code == 201
    poll_id = created.json()["poll"]["id"]
    message_id = created.json()["id"]

    bob_client, bob_csrf = await _client_for(app, "u-bob")
    multi_vote = await bob_client.put(
        f"/api/groups/{group_id}/polls/{poll_id}/vote",
        json={"option_indexes": [0, 2]},
        headers={"x-csrf-token": bob_csrf},
    )
    assert multi_vote.status_code == 200
    assert multi_vote.json()["my_votes"] == [0, 2]

    forward = await owner_client.post(
        f"/api/groups/{group_id}/forward",
        json={"message_id": message_id},
        headers={"x-csrf-token": owner_csrf},
    )
    assert forward.status_code == 422
    await owner_client.aclose()
    await bob_client.aclose()
