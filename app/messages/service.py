from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends
from app.models import Message, User
from app.timeutil import iso_utc

MAX_MESSAGE_LENGTH = 2000
HISTORY_DEFAULT_LIMIT = 50
HISTORY_MAX_LIMIT = 100


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def message_payload(message: Message) -> dict[str, str | int]:
    return {
        "id": message.id,
        "sender_sub": message.sender_sub,
        "recipient_sub": message.recipient_sub,
        "content": message.content,
        "created_at": iso_utc(message.created_at),
    }


async def send_message(
    db: AsyncSession, sender_sub: str, recipient_sub: str, content: str
) -> Message:
    if sender_sub == recipient_sub:
        raise HTTPException(status_code=400, detail="cannot message yourself")
    if await db.get(User, recipient_sub) is None:
        raise HTTPException(status_code=404, detail="user not found")
    if not await are_friends(db, sender_sub, recipient_sub):
        raise HTTPException(status_code=403, detail="not friends")
    lo, hi = pair_key(sender_sub, recipient_sub)
    message = Message(
        sender_sub=sender_sub,
        recipient_sub=recipient_sub,
        participant_lo=lo,
        participant_hi=hi,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def history(
    db: AsyncSession,
    me_sub: str,
    other_sub: str,
    *,
    before: int | None = None,
    limit: int = HISTORY_DEFAULT_LIMIT,
) -> tuple[list[Message], int | None]:
    lo, hi = pair_key(me_sub, other_sub)
    stmt = (
        select(Message)
        .where(Message.participant_lo == lo, Message.participant_hi == hi)
        .order_by(Message.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        stmt = stmt.where(Message.id < before)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    page = list(rows[:limit])
    next_before = page[-1].id if has_more and page else None
    return page, next_before
