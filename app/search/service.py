from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.friends import service as friends_service
from app.models import Group, GroupMember, Message, User
from app.timeutil import iso_utc

SEARCH_DEFAULT_LIMIT = 20
SEARCH_MAX_LIMIT = 50


def make_snippet(content: str, query: str, width: int = 40) -> str:
    index = content.lower().find(query.lower())
    if index < 0:
        index = 0
    start = max(0, index - width)
    end = min(len(content), index + len(query) + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    return f"{prefix}{content[start:end]}{suffix}"


async def search_messages(
    db: AsyncSession,
    me_sub: str,
    query: str,
    *,
    before: int | None = None,
    limit: int = SEARCH_DEFAULT_LIMIT,
) -> tuple[list[dict[str, Any]], int | None]:
    group_ids = (
        await db.execute(
            select(GroupMember.group_id).where(GroupMember.user_sub == me_sub)
        )
    ).scalars().all()
    pattern = f"%{query}%"
    stmt = (
        select(Message)
        .where(
            Message.deleted_at.is_(None),
            Message.content.ilike(pattern),
            or_(
                and_(
                    Message.conversation_type == "dm",
                    or_(
                        Message.participant_lo == me_sub,
                        Message.participant_hi == me_sub,
                    ),
                ),
                and_(
                    Message.conversation_type == "group",
                    Message.group_id.in_(list(group_ids)),
                ),
            ),
        )
        .order_by(Message.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        stmt = stmt.where(Message.id < before)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    page = list(rows[:limit])
    peer_subs = {
        row.sender_sub if row.sender_sub != me_sub else row.recipient_sub
        for row in page
        if row.conversation_type == "dm"
    }
    group_ids_in_page = {
        row.group_id for row in page if row.group_id is not None
    }
    users: dict[str, User] = {}
    groups: dict[int, Group] = {}
    if peer_subs:
        found = (
            await db.execute(select(User).where(User.sub.in_(list(peer_subs))))
        ).scalars().all()
        users = {user.sub: user for user in found}
    if group_ids_in_page:
        found_groups = (
            await db.execute(select(Group).where(Group.id.in_(list(group_ids_in_page))))
        ).scalars().all()
        groups = {group.id: group for group in found_groups}
    items: list[dict[str, Any]] = []
    for row in page:
        if row.conversation_type == "group":
            group = groups.get(row.group_id) if row.group_id is not None else None
            conversation: dict[str, Any] = {
                "type": "group",
                "group_id": row.group_id,
                "group_name": group.name if group is not None else None,
                "peer_sub": None,
                "peer_name": None,
            }
        else:
            peer = row.sender_sub if row.sender_sub != me_sub else row.recipient_sub
            peer_user = users.get(peer)
            conversation = {
                "type": "dm",
                "peer_sub": peer,
                "peer_name": (
                    (peer_user.nickname or peer_user.name or peer)
                    if peer_user is not None
                    else peer
                ),
                "group_id": None,
                "group_name": None,
            }
        items.append(
            {
                "id": row.id,
                "sender_sub": row.sender_sub,
                "conversation": conversation,
                "snippet": make_snippet(row.content, query),
                "created_at": iso_utc(row.created_at),
            }
        )
    next_before = page[-1].id if has_more and page else None
    return items, next_before


async def search_contacts(
    db: AsyncSession, me_sub: str, query: str, *, limit: int = SEARCH_DEFAULT_LIMIT
) -> list[dict[str, Any]]:
    return await friends_service.search_users(db, me_sub, query, limit=limit)
