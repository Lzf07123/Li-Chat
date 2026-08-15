from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthState, Friendship, Message, Session, User
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


async def test_friendship_roundtrip(db_session: AsyncSession) -> None:
    db_session.add_all([User(sub="u-1", nickname="Alice"), User(sub="u-2", nickname="Bob")])
    await db_session.flush()
    db_session.add(Friendship(requester_sub="u-1", addressee_sub="u-2", status="pending"))
    await db_session.commit()
    row = (
        await db_session.execute(
            select(Friendship).where(Friendship.requester_sub == "u-1")
        )
    ).scalar_one()
    assert row.addressee_sub == "u-2"
    assert row.status == "pending"
    assert row.created_at is not None


async def test_friendship_self_pair_rejected(db_session: AsyncSession) -> None:
    db_session.add(User(sub="u-1", nickname="Alice"))
    await db_session.flush()
    db_session.add(Friendship(requester_sub="u-1", addressee_sub="u-1", status="pending"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_message_roundtrip(db_session: AsyncSession) -> None:
    db_session.add_all([User(sub="u-1", nickname="Alice"), User(sub="u-2", nickname="Bob")])
    await db_session.flush()
    db_session.add(
        Message(
            sender_sub="u-1",
            recipient_sub="u-2",
            participant_lo="u-1",
            participant_hi="u-2",
            content="hello",
        )
    )
    await db_session.commit()
    row = (await db_session.execute(select(Message))).scalar_one()
    assert row.id is not None
    assert row.sender_sub == "u-1"
    assert row.content == "hello"
    assert row.created_at is not None


async def test_message_participant_order_rejected(db_session: AsyncSession) -> None:
    db_session.add_all([User(sub="u-1", nickname="Alice"), User(sub="u-2", nickname="Bob")])
    await db_session.flush()
    db_session.add(
        Message(
            sender_sub="u-1",
            recipient_sub="u-2",
            participant_lo="u-2",
            participant_hi="u-1",
            content="bad order",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
