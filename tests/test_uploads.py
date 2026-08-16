from __future__ import annotations

from typing import Any

import httpx

from tests.fixtures.chat import make_friends, seed_session, seed_user

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
)
PDF_BYTES = b"%PDF-1.4\n" + b"\x00" * 16
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'


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


async def _upload(
    client: httpx.AsyncClient,
    csrf: str,
    name: str,
    data: bytes,
    mime: str,
) -> httpx.Response:
    return await client.post(
        "/api/uploads",
        files={"file": (name, data, mime)},
        headers={"x-csrf-token": csrf},
    )


async def test_upload_image_and_download(app: Any) -> None:
    alice, csrf = await _client_for(app, "u-alice")
    async with alice:
        uploaded = await _upload(alice, csrf, "photo.png", PNG_BYTES, "image/png")
        assert uploaded.status_code == 201
        body = uploaded.json()
        assert body["mime"] == "image/png"
        assert body["size"] == len(PNG_BYTES)
        assert body["url"].startswith("/api/uploads/")
        downloaded = await alice.get(body["url"])
    assert downloaded.status_code == 200
    assert downloaded.content == PNG_BYTES
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert "inline" in downloaded.headers["content-disposition"]


async def test_upload_validation_and_access_control(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-alice", nickname="Alice")
        await seed_user(db, "u-bob", nickname="Bob")
    alice, csrf = await _client_for(app, "u-alice")
    bob, _ = await _client_for(app, "u-bob")
    anon = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    async with alice, bob, anon:
        fake = await _upload(alice, csrf, "evil.png", SVG_BYTES, "image/png")
        assert fake.status_code == 415
        pdf = await _upload(alice, csrf, "doc.pdf", PDF_BYTES, "application/pdf")
        assert pdf.status_code == 201
        url = pdf.json()["url"]
        stranger = await bob.get(url)
        anonymous = await anon.get(url)
        traversal = await alice.get("/api/uploads/../etc/passwd")
    assert stranger.status_code == 403
    assert anonymous.status_code == 401
    assert traversal.status_code == 404


async def test_upload_size_limit(app: Any) -> None:
    alice, csrf = await _client_for(app, "u-alice")
    settings = app.state.settings
    limit = settings.upload_max_mb
    async with alice:
        big = await _upload(
            alice,
            csrf,
            "big.bin",
            b"\x89PNG\r\n\x1a\n" + b"\x00" * (limit * 1024 * 1024),
            "image/png",
        )
    assert big.status_code == 413


async def test_image_message_send_and_history(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, alice_csrf = await _client_for(app, "u-alice")
    async with alice:
        uploaded = await _upload(alice, alice_csrf, "pic.png", PNG_BYTES, "image/png")
        assert uploaded.status_code == 201
        url = uploaded.json()["url"]
        sent = await alice.post(
            "/api/conversations/u-bob/messages",
            json={
                "content": "看图",
                "content_type": "image",
                "attachment": {"url": url},
            },
            headers={"x-csrf-token": alice_csrf},
        )
    assert sent.status_code == 201
    body = sent.json()
    assert body["content_type"] == "image"
    assert body["attachment"]["url"] == url
    bob, _ = await _client_for(app, "u-bob")
    async with bob:
        history = await bob.get("/api/conversations/u-alice/messages")
    item = history.json()["messages"][0]
    assert item["content_type"] == "image"
    assert item["attachment"]["name"] == "pic.png"


async def test_attachment_must_belong_to_sender(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    await _make_friends(app, "u-alice", "u-carol")
    alice, alice_csrf = await _client_for(app, "u-alice")
    carol, carol_csrf = await _client_for(app, "u-carol")
    async with alice, carol:
        uploaded = await _upload(alice, alice_csrf, "mine.png", PNG_BYTES, "image/png")
        url = uploaded.json()["url"]
        # 好友关系没问题，但借用他人附件会被归属校验拒绝（403）
        stolen = await carol.post(
            "/api/conversations/u-alice/messages",
            json={
                "content": "借用",
                "content_type": "image",
                "attachment": {"url": url},
            },
            headers={"x-csrf-token": carol_csrf},
        )
    assert stolen.status_code == 403


async def test_attachment_message_requires_attachment(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    alice, csrf = await _client_for(app, "u-alice")
    async with alice:
        missing = await alice.post(
            "/api/conversations/u-bob/messages",
            json={"content": "无附件", "content_type": "image"},
            headers={"x-csrf-token": csrf},
        )
    assert missing.status_code == 422
