from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthState, Session, User
from app.timeutil import utcnow


async def test_user_roundtrip(db_session: AsyncSession) -> None:
    db_session.add(User(sub="u-1", nickname="Alice"))
    await db_session.commit()
    user = (await db_session.execute(select(User).where(User.sub == "u-1"))).scalar_one()
    assert user.nickname == "Alice"
    assert user.created_at is not None


async def test_auth_state_roundtrip(db_session: AsyncSession) -> None:
    state = AuthState(
        state="s-1",
        verifier="v-1",
        nonce="n-1",
        redirect_after="/",
        expires_at=utcnow() + timedelta(minutes=10),
    )
    db_session.add(state)
    await db_session.commit()
    found = (
        await db_session.execute(select(AuthState).where(AuthState.state == "s-1"))
    ).scalar_one()
    assert found.nonce == "n-1"


async def test_session_roundtrip(db_session: AsyncSession) -> None:
    db_session.add(User(sub="u-1", nickname="Alice"))
    await db_session.flush()
    now = utcnow()
    db_session.add(
        Session(
            id="session-1",
            user_sub="u-1",
            sid="sid-1",
            acr="urn:lipass:acr:2fa",
            csrf_token="csrf-1",
            expires_at=now + timedelta(hours=2),
            absolute_expires_at=now + timedelta(days=7),
        )
    )
    await db_session.commit()
    found = (
        await db_session.execute(select(Session).where(Session.id == "session-1"))
    ).scalar_one()
    assert found.user_sub == "u-1"
    assert found.acr == "urn:lipass:acr:2fa"
