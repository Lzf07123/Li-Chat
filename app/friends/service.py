from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Friendship, User

SEARCH_RESULT_LIMIT = 20


def profile(user: User) -> dict[str, str | None]:
    return {
        "sub": user.sub,
        "nickname": user.nickname,
        "name": user.name,
        "picture": user.picture,
    }


async def _pair_row(db: AsyncSession, a: str, b: str) -> Friendship | None:
    return (
        await db.execute(
            select(Friendship).where(
                or_(
                    and_(Friendship.requester_sub == a, Friendship.addressee_sub == b),
                    and_(Friendship.requester_sub == b, Friendship.addressee_sub == a),
                )
            )
        )
    ).scalar_one_or_none()


async def friend_status(db: AsyncSession, me_sub: str, other_sub: str) -> str:
    row = await _pair_row(db, me_sub, other_sub)
    if row is None:
        return "none"
    if row.status == "accepted":
        return "friends"
    return "outgoing" if row.requester_sub == me_sub else "incoming"


async def search_users(
    db: AsyncSession,
    me_sub: str,
    query: str,
    *,
    limit: int = SEARCH_RESULT_LIMIT,
) -> list[dict[str, Any]]:
    pattern = f"%{query}%"
    users = (
        await db.execute(
            select(User)
            .where(User.sub != me_sub)
            .where(or_(User.nickname.ilike(pattern), User.email.ilike(pattern)))
            .order_by(User.nickname, User.sub)
            .limit(limit)
        )
    ).scalars().all()
    return [
        {**profile(user), "friend_status": await friend_status(db, me_sub, user.sub)}
        for user in users
    ]
