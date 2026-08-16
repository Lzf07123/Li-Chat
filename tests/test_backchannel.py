import time

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import create_session
from app.models import Session, User
from tests.fixtures.mock_idp import MockIdP

_EVENT = "http://schemas.openid.net/event/backchannel-logout"


class FakeWS:
    def __init__(self) -> None:
        self.closed_with: list[int] = []

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed_with.append(code)

    async def send_json(self, data, mode: str = "text") -> None:
        pass


async def _seed_sessions(db_session: AsyncSession) -> dict[str, str]:
    db_session.add(User(sub="u-1", nickname="A"))
    await db_session.commit()
    s1 = await create_session(db_session, "u-1", sid="sid-1")
    s2 = await create_session(db_session, "u-1", sid="sid-2")
    return {"drop": s1.id, "keep": s2.id}


async def _register_fake_ws(app, fake: FakeWS) -> None:
    await app.state.ws_manager.connect("u-1", fake)


def _logout_token(mock_idp: MockIdP, jti: str, **overrides) -> str:
    claims = {
        "sub": "u-1",
        "sid": "sid-1",
        "jti": jti,
        "events": {_EVENT: {}},
        **overrides,
    }
    return mock_idp.sign_logout_token(claims)


async def test_valid_logout_token_clears_sessions_and_closes_ws(
    app,
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    mock_idp: MockIdP,
) -> None:
    ids = await _seed_sessions(db_session)
    fake = FakeWS()
    await _register_fake_ws(app, fake)
    response = await api_client.post(
        "/oidc/backchannel-logout", data={"logout_token": _logout_token(mock_idp, "j-1")}
    )
    assert response.status_code == 200
    remaining = (await db_session.execute(select(Session.id))).scalars().all()
    assert remaining == [ids["keep"]]
    assert fake.closed_with == [4401]


async def test_replayed_jti_is_ignored(
    app,
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    mock_idp: MockIdP,
) -> None:
    ids = await _seed_sessions(db_session)
    fake = FakeWS()
    await _register_fake_ws(app, fake)
    token = _logout_token(mock_idp, "j-2")
    first = await api_client.post("/oidc/backchannel-logout", data={"logout_token": token})
    assert first.status_code == 200
    await create_session(db_session, "u-1", sid="sid-1")
    second = await api_client.post("/oidc/backchannel-logout", data={"logout_token": token})
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
    remaining = (await db_session.execute(select(Session.id))).scalars().all()
    assert ids["keep"] in remaining
    assert len(remaining) == 2
    assert fake.closed_with == [4401]


async def test_wrong_audience_rejected(
    api_client: httpx.AsyncClient, mock_idp: MockIdP
) -> None:
    token = _logout_token(mock_idp, "j-3", aud="other-client")
    response = await api_client.post("/oidc/backchannel-logout", data={"logout_token": token})
    assert response.status_code == 400


async def test_stale_token_rejected(
    api_client: httpx.AsyncClient, mock_idp: MockIdP
) -> None:
    token = _logout_token(mock_idp, "j-4", iat=int(time.time()) - 300)
    response = await api_client.post("/oidc/backchannel-logout", data={"logout_token": token})
    assert response.status_code == 400


async def test_missing_logout_event_rejected(
    api_client: httpx.AsyncClient, mock_idp: MockIdP
) -> None:
    token = _logout_token(mock_idp, "j-5", events={})
    response = await api_client.post("/oidc/backchannel-logout", data={"logout_token": token})
    assert response.status_code == 400


async def test_logout_token_with_unmatched_sid_clears_all_sessions_for_user(
    app,
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    mock_idp: MockIdP,
) -> None:
    await _seed_sessions(db_session)
    fake = FakeWS()
    await _register_fake_ws(app, fake)
    token = _logout_token(mock_idp, "j-r1", sid="sid-rotated")
    response = await api_client.post("/oidc/backchannel-logout", data={"logout_token": token})
    assert response.status_code == 200
    assert (await db_session.execute(select(Session.id))).scalars().all() == []
    assert fake.closed_with == [4401]


async def test_logout_token_without_sid_clears_all_sessions_for_user(
    app,
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    mock_idp: MockIdP,
) -> None:
    await _seed_sessions(db_session)
    fake = FakeWS()
    await _register_fake_ws(app, fake)
    token = _logout_token(mock_idp, "j-r2", sid=None)
    response = await api_client.post("/oidc/backchannel-logout", data={"logout_token": token})
    assert response.status_code == 200
    assert (await db_session.execute(select(Session.id))).scalars().all() == []
    assert fake.closed_with == [4401]
