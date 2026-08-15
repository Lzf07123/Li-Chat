from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import (
    create_session,
    delete_session,
    delete_sessions_for,
    get_session,
)
from app.models import Session, User
from app.timeutil import utcnow


async def _add_user(db: AsyncSession) -> None:
    db.add(User(sub="u-1", nickname="Alice"))
    await db.commit()


async def test_create_and_get_session(db_session: AsyncSession) -> None:
    await _add_user(db_session)
    session = await create_session(
        db_session, "u-1", sid="sid-1", acr="urn:lipass:acr:2fa"
    )
    assert session.csrf_token
    loaded = await get_session(db_session, session.id, sliding_ttl=7200)
    assert loaded is not None
    assert loaded.user_sub == "u-1"
    assert loaded.sid == "sid-1"


async def test_get_session_slides_expiry(db_session: AsyncSession) -> None:
    await _add_user(db_session)
    session = await create_session(db_session, "u-1", sliding_ttl=100, absolute_ttl=1000)
    session.expires_at = utcnow() + timedelta(seconds=1)
    await db_session.commit()
    loaded = await get_session(db_session, session.id, sliding_ttl=100)
    assert loaded is not None
    assert loaded.expires_at > utcnow() + timedelta(seconds=50)


async def test_expired_session_returns_none(db_session: AsyncSession) -> None:
    await _add_user(db_session)
    session = await create_session(db_session, "u-1")
    session.expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    assert await get_session(db_session, session.id, sliding_ttl=7200) is None


async def test_absolute_expired_session_returns_none(db_session: AsyncSession) -> None:
    await _add_user(db_session)
    session = await create_session(db_session, "u-1")
    session.absolute_expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    assert await get_session(db_session, session.id, sliding_ttl=7200) is None


async def test_delete_session(db_session: AsyncSession) -> None:
    await _add_user(db_session)
    session = await create_session(db_session, "u-1")
    await delete_session(db_session, session.id)
    assert await get_session(db_session, session.id, sliding_ttl=7200) is None


async def test_delete_sessions_for_sub_and_sid(db_session: AsyncSession) -> None:
    await _add_user(db_session)
    keep = await create_session(db_session, "u-1", sid="sid-1")
    drop1 = await create_session(db_session, "u-1", sid="sid-2")
    drop2 = await create_session(db_session, "u-1", sid="sid-2")
    await delete_sessions_for(db_session, "u-1", "sid-2")
    remaining = (
        (await db_session.execute(select(Session.id))).scalars().all()
    )
    assert set(remaining) == {keep.id}
    assert drop1.id not in remaining
    assert drop2.id not in remaining
