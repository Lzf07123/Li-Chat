from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import create_session
from app.models import Friendship, User


async def seed_user(
    db: AsyncSession,
    sub: str,
    *,
    nickname: str | None = None,
    email: str | None = None,
) -> User:
    user = await db.get(User, sub)
    if user is None:
        user = User(sub=sub, nickname=nickname, email=email)
        db.add(user)
        await db.commit()
    return user


async def seed_session(app: Any, sub: str) -> tuple[str, str]:
    """种子用户 + 会话，返回 (session_id, csrf_token)。"""
    async with app.state.session_factory() as db:
        await seed_user(db, sub)
        session = await create_session(db, sub)
        return session.id, session.csrf_token


async def make_friends(db: AsyncSession, a: str, b: str) -> None:
    await seed_user(db, a, nickname=a)
    await seed_user(db, b, nickname=b)
    db.add(Friendship(requester_sub=a, addressee_sub=b, status="accepted"))
    await db.commit()


def seed_session_sync(app: Any, sub: str) -> tuple[str, str]:
    return asyncio.run(seed_session(app, sub))


def make_friends_sync(app: Any, a: str, b: str) -> None:
    async def run() -> None:
        async with app.state.session_factory() as db:
            await make_friends(db, a, b)

    asyncio.run(run())
