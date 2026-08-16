from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, User
from app.timeutil import iso_utc, utcnow

NOTIFICATION_TYPES = frozenset(
    {
        "friend_request",
        "mention",
        "muted",
        "unmuted",
        "role_changed",
        "group_dissolved",
    }
)


async def create(
    db: AsyncSession,
    user_sub: str,
    type_: str,
    *,
    actor_sub: str | None = None,
    group_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> Notification:
    if type_ not in NOTIFICATION_TYPES:
        raise ValueError(f"unknown notification type: {type_}")
    notification = Notification(
        user_sub=user_sub,
        type=type_,
        actor_sub=actor_sub,
        group_id=group_id,
        payload=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


def notification_payload(
    notification: Notification, actor: User | None = None
) -> dict[str, Any]:
    try:
        data = json.loads(notification.payload or "{}")
    except (TypeError, ValueError):
        data = {}
    group = (
        {"id": notification.group_id, "name": data.get("group_name")}
        if notification.group_id is not None
        else None
    )
    return {
        "id": notification.id,
        "type": notification.type,
        "actor": (
            {
                "sub": actor.sub,
                "nickname": actor.nickname,
                "name": actor.name,
                "picture": actor.picture,
            }
            if actor is not None
            else None
        ),
        "group": group,
        "payload": data,
        "read": notification.read_at is not None,
        "created_at": iso_utc(notification.created_at),
    }


async def list_for(
    db: AsyncSession,
    user_sub: str,
    *,
    cursor: int | None = None,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int | None, int]:
    stmt = (
        select(Notification)
        .where(Notification.user_sub == user_sub)
        .order_by(Notification.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(Notification.id < cursor)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    page = list(rows[:limit])
    unread = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_sub == user_sub,
                    Notification.read_at.is_(None),
                )
            )
        ).scalar_one()
    )
    actor_subs = {row.actor_sub for row in page if row.actor_sub is not None}
    actors: dict[str, User] = {}
    if actor_subs:
        found = (
            await db.execute(select(User).where(User.sub.in_(actor_subs)))
        ).scalars().all()
        actors = {user.sub: user for user in found}
    items = [
        notification_payload(row, actors.get(row.actor_sub) if row.actor_sub else None)
        for row in page
    ]
    next_cursor = page[-1].id if has_more and page else None
    return items, next_cursor, unread


async def mark_all_read(db: AsyncSession, user_sub: str) -> None:
    rows = (
        await db.execute(
            select(Notification).where(
                Notification.user_sub == user_sub,
                Notification.read_at.is_(None),
            )
        )
    ).scalars().all()
    for row in rows:
        row.read_at = utcnow()
    await db.commit()
