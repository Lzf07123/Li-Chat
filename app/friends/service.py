from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Friendship, User
from app.timeutil import iso_utc

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


async def send_request(
    db: AsyncSession, requester_sub: str, addressee_sub: str
) -> Friendship:
    if requester_sub == addressee_sub:
        raise HTTPException(status_code=400, detail="cannot send friend request to yourself")
    if await db.get(User, addressee_sub) is None:
        raise HTTPException(status_code=404, detail="user not found")
    existing = await _pair_row(db, requester_sub, addressee_sub)
    if existing is not None:
        if existing.status == "accepted":
            raise HTTPException(status_code=409, detail="already friends")
        if existing.requester_sub == requester_sub:
            raise HTTPException(status_code=409, detail="friend request already sent")
        raise HTTPException(status_code=409, detail="incoming friend request already exists")
    friendship = Friendship(
        requester_sub=requester_sub, addressee_sub=addressee_sub, status="pending"
    )
    db.add(friendship)
    await db.commit()
    await db.refresh(friendship)
    return friendship


async def list_requests(db: AsyncSession, me_sub: str) -> dict[str, list[dict[str, Any]]]:
    rows = (
        await db.execute(
            select(Friendship)
            .where(Friendship.status == "pending")
            .where(
                or_(
                    Friendship.requester_sub == me_sub,
                    Friendship.addressee_sub == me_sub,
                )
            )
            .order_by(Friendship.created_at.desc())
        )
    ).scalars().all()
    subs = {
        row.requester_sub if row.addressee_sub == me_sub else row.addressee_sub
        for row in rows
    }
    users: dict[str, User] = {}
    if subs:
        found = (await db.execute(select(User).where(User.sub.in_(subs)))).scalars().all()
        users = {user.sub: user for user in found}
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for row in rows:
        if row.requester_sub == me_sub:
            other = users.get(row.addressee_sub)
            if other is not None:
                outgoing.append(
                    {"addressee": profile(other), "created_at": iso_utc(row.created_at)}
                )
        else:
            other = users.get(row.requester_sub)
            if other is not None:
                incoming.append(
                    {"requester": profile(other), "created_at": iso_utc(row.created_at)}
                )
    return {"incoming": incoming, "outgoing": outgoing}
