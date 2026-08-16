from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends, list_friends
from app.models import DmRead, Message, User
from app.timeutil import iso_utc, utcnow

MAX_MESSAGE_LENGTH = 2000
HISTORY_DEFAULT_LIMIT = 50
HISTORY_MAX_LIMIT = 100
EDIT_WINDOW_SECONDS = 300


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def message_payload(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": message.id,
        "sender_sub": message.sender_sub,
        "recipient_sub": message.recipient_sub,
        "created_at": iso_utc(message.created_at),
    }
    if message.deleted_at is not None:
        payload["deleted"] = True
    else:
        payload["deleted"] = False
        payload["content"] = message.content
        if message.edited_at is not None:
            payload["edited_at"] = iso_utc(message.edited_at)
    return payload


async def _advance_read(
    db: AsyncSession, user_sub: str, lo: str, hi: str, message_id: int
) -> None:
    row = await db.get(DmRead, (user_sub, lo, hi))
    if row is None:
        db.add(
            DmRead(
                user_sub=user_sub,
                participant_lo=lo,
                participant_hi=hi,
                last_read_message_id=message_id,
            )
        )
    elif message_id > row.last_read_message_id:
        row.last_read_message_id = message_id


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
    await db.flush()
    await _advance_read(db, sender_sub, lo, hi, message.id)
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


async def conversation_summaries(db: AsyncSession, me_sub: str) -> list[dict[str, Any]]:
    friends = await list_friends(db, me_sub)
    subs = [friend["sub"] for friend in friends if friend["sub"] is not None]
    reads: dict[str, DmRead] = {}
    if subs:
        read_rows = (
            await db.execute(
                select(DmRead).where(
                    DmRead.user_sub == me_sub,
                    or_(
                        and_(
                            DmRead.participant_lo == me_sub,
                            DmRead.participant_hi.in_(subs),
                        ),
                        and_(
                            DmRead.participant_hi == me_sub,
                            DmRead.participant_lo.in_(subs),
                        ),
                    ),
                )
            )
        ).scalars().all()
        reads = {
            row.participant_hi if row.participant_lo == me_sub else row.participant_lo: row
            for row in read_rows
        }
    last_by_peer: dict[str, Message] = {}
    unread_by_peer: dict[str, int] = {}
    if subs:
        rows = (
            await db.execute(
                select(Message)
                .where(
                    or_(
                        and_(
                            Message.participant_lo == me_sub,
                            Message.participant_hi.in_(subs),
                        ),
                        and_(
                            Message.participant_hi == me_sub,
                            Message.participant_lo.in_(subs),
                        ),
                    )
                )
                .order_by(Message.id.desc())
            )
        ).scalars().all()
        for message in rows:
            peer = (
                message.recipient_sub
                if message.sender_sub == me_sub
                else message.sender_sub
            )
            last_by_peer.setdefault(peer, message)
            if message.sender_sub != me_sub:
                cursor = reads.get(peer)
                last_read_id = cursor.last_read_message_id if cursor else 0
                if message.id > last_read_id:
                    unread_by_peer[peer] = unread_by_peer.get(peer, 0) + 1
    summaries: list[dict[str, Any]] = []
    for friend in friends:
        friend_sub = friend["sub"]
        last = last_by_peer.get(friend_sub) if friend_sub is not None else None
        cursor = reads.get(friend_sub) if friend_sub is not None else None
        summaries.append(
            {
                "peer": friend,
                "last_message": message_payload(last) if last is not None else None,
                "unread_count": (
                    unread_by_peer.get(friend_sub, 0) if friend_sub is not None else 0
                ),
                "last_read_id": cursor.last_read_message_id if cursor is not None else 0,
            }
        )
    summaries.sort(
        key=lambda item: (
            item["last_message"]["id"] if item["last_message"] is not None else -1
        ),
        reverse=True,
    )
    return summaries


async def mark_read(
    db: AsyncSession, me_sub: str, other_sub: str, last_read_id: int
) -> None:
    if not await are_friends(db, me_sub, other_sub):
        raise HTTPException(status_code=403, detail="not friends")
    lo, hi = pair_key(me_sub, other_sub)
    message = await db.get(Message, last_read_id)
    if message is None or (message.participant_lo, message.participant_hi) != (lo, hi):
        raise HTTPException(status_code=404, detail="message not found in conversation")
    row = await db.get(DmRead, (me_sub, lo, hi))
    if row is None:
        db.add(
            DmRead(
                user_sub=me_sub,
                participant_lo=lo,
                participant_hi=hi,
                last_read_message_id=last_read_id,
            )
        )
    elif last_read_id > row.last_read_message_id:
        row.last_read_message_id = last_read_id
    await db.commit()


async def _own_editable_message(
    db: AsyncSession, me_sub: str, other_sub: str, message_id: int
) -> Message:
    lo, hi = pair_key(me_sub, other_sub)
    message = await db.get(Message, message_id)
    if message is None or (message.participant_lo, message.participant_hi) != (lo, hi):
        raise HTTPException(status_code=404, detail="message not found in conversation")
    if message.sender_sub != me_sub:
        raise HTTPException(status_code=403, detail="only the sender can modify this message")
    if message.deleted_at is not None:
        raise HTTPException(status_code=409, detail="message already deleted")
    if utcnow() - message.created_at > timedelta(seconds=EDIT_WINDOW_SECONDS):
        raise HTTPException(status_code=409, detail="edit window expired")
    return message


async def edit_message(
    db: AsyncSession, me_sub: str, other_sub: str, message_id: int, content: str
) -> Message:
    message = await _own_editable_message(db, me_sub, other_sub, message_id)
    message.content = content
    message.edited_at = utcnow()
    await db.commit()
    await db.refresh(message)
    return message


async def delete_message(
    db: AsyncSession, me_sub: str, other_sub: str, message_id: int
) -> Message:
    message = await _own_editable_message(db, me_sub, other_sub, message_id)
    message.content = ""
    message.deleted_at = utcnow()
    await db.commit()
    await db.refresh(message)
    return message
