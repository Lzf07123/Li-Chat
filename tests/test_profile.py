from __future__ import annotations

from typing import Any

import httpx

from tests.fixtures.chat import make_friends, seed_session

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PDF_BYTES = b"%PDF-1.4\n" + b"\x00" * 8


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def _make_friends(app: Any, a: str, b: str) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, a, b)


async def test_update_nickname_and_bio(app: Any) -> None:
    alice, csrf = await _client_for(app, "u-alice")
    async with alice:
        updated = await alice.patch(
            "/api/me",
            json={"nickname": "小艾", "bio": "爱写代码"},
            headers={"x-csrf-token": csrf},
        )
        assert updated.status_code == 200
        me = (await alice.get("/api/me")).json()
        blank = await alice.patch(
            "/api/me", json={"nickname": "   "}, headers={"x-csrf-token": csrf}
        )
        long_bio = await alice.patch(
            "/api/me",
            json={"bio": "长" * 201},
            headers={"x-csrf-token": csrf},
        )
    assert me["nickname"] == "小艾"
    assert me["bio"] == "爱写代码"
    assert blank.status_code == 422
    assert long_bio.status_code == 422


async def test_avatar_rules(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, bob_csrf = await _client_for(app, "u-bob")
    async with alice, bob:
        image = await alice.post(
            "/api/uploads",
            files={"file": ("a.png", PNG_BYTES, "image/png")},
            headers={"x-csrf-token": alice_csrf},
        )
        pdf = await alice.post(
            "/api/uploads",
            files={"file": ("d.pdf", PDF_BYTES, "application/pdf")},
            headers={"x-csrf-token": alice_csrf},
        )
        assert image.status_code == 201
        assert pdf.status_code == 201
        image_url = image.json()["url"]
        pdf_url = pdf.json()["url"]
        set_avatar = await alice.post(
            "/api/me/avatar",
            json={"url": image_url},
            headers={"x-csrf-token": alice_csrf},
        )
        assert set_avatar.status_code == 200
        assert set_avatar.json()["picture"] == image_url
        not_image = await alice.post(
            "/api/me/avatar",
            json={"url": pdf_url},
            headers={"x-csrf-token": alice_csrf},
        )
        stolen = await bob.post(
            "/api/me/avatar",
            json={"url": image_url},
            headers={"x-csrf-token": bob_csrf},
        )
        bad_url = await alice.post(
            "/api/me/avatar",
            json={"url": "/etc/passwd"},
            headers={"x-csrf-token": alice_csrf},
        )
    assert not_image.status_code == 422
    assert stolen.status_code == 403
    assert bad_url.status_code == 422


async def test_bio_only_visible_to_friends(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    bob, _ = await _client_for(app, "u-bob")
    async with alice, bob:
        await alice.patch(
            "/api/me",
            json={"bio": "只给朋友看"},
            headers={"x-csrf-token": alice_csrf},
        )
        friends = await bob.get("/api/friends")
        search = await bob.get("/api/users/search", params={"q": "alice"})
    friend_item = friends.json()["friends"][0]
    search_item = search.json()["results"][0]
    assert friend_item["bio"] == "只给朋友看"
    assert "bio" not in search_item
