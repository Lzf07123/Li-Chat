import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth.session import create_session
from app.models import User


def _seed_session(app, sid: str = "sid-1") -> str:
    async def seed() -> str:
        async with app.state.session_factory() as db:
            db.add(User(sub="u-1", nickname="Alice"))
            session = await create_session(db, "u-1", sid=sid)
            return session.id

    return asyncio.run(seed())


def test_ws_without_session_is_rejected(app) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4401


def test_ws_with_session_receives_hello_and_pong(app) -> None:
    session_id = _seed_session(app)
    with TestClient(app) as client:
        client.cookies.set("lichat_session", session_id)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-1"}
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}
