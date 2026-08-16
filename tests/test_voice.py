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


async def test_upload_and_send_voice_message(app: Any) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    webm = b"\x1aE\xdf\xa3" + b"\x00" * 64
    upload = await client.post(
        "/api/uploads",
        files={"file": ("voice.webm", webm, "audio/webm")},
        headers={"x-csrf-token": csrf},
    )
    assert upload.status_code == 201
    assert upload.json()["mime"] == "audio/webm"

    sent = await client.post(
        "/api/conversations/u-bob/messages",
        json={
            "content": "",
            "content_type": "audio",
            "attachment": {"url": upload.json()["url"]},
        },
        headers={"x-csrf-token": csrf},
    )
    assert sent.status_code == 201
    body = sent.json()
    assert body["content_type"] == "audio"
    assert body["attachment"]["mime"] == "audio/webm"

    history = await client.get("/api/conversations/u-bob/messages")
    assert history.status_code == 200
    assert history.json()["messages"][0]["content_type"] == "audio"
    await client.aclose()


async def test_audio_mp4_accepted_and_garbage_rejected(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    mp4 = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 64
    good = await client.post(
        "/api/uploads",
        files={"file": ("voice.m4a", mp4, "audio/mp4")},
        headers={"x-csrf-token": csrf},
    )
    assert good.status_code == 201
    assert good.json()["mime"] == "audio/mp4"

    garbage = await client.post(
        "/api/uploads",
        files={"file": ("fake.webm", b"\x00\x01\x02" * 32, "audio/webm")},
        headers={"x-csrf-token": csrf},
    )
    assert garbage.status_code == 415
    await client.aclose()
