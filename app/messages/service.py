from __future__ import annotations

import unicodedata
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends, list_friends
from app.groups.service import membership as group_membership
from app.models import (
    DmRead,
    Group,
    GroupMember,
    GroupRead,
    Message,
    MessageMention,
    Reaction,
    User,
    UserConversationSetting,
    UserStar,
)
from app.timeutil import iso_utc, utcnow
from app.uploads.service import get_upload

MAX_MESSAGE_LENGTH = 2000
HISTORY_DEFAULT_LIMIT = 50
HISTORY_MAX_LIMIT = 100
EDIT_WINDOW_SECONDS = 300
EMOJI_MAX_LENGTH = 8
GROUP_RECIPIENT_PREFIX = "group:"
MAX_MENTIONS = 50


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def dm_key(a: str, b: str) -> str:
    lo, hi = pair_key(a, b)
    return f"{lo}:{hi}"


def message_payload(
    message: Message,
    reply: Message | None = None,
    mentions: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": message.id,
        "sender_sub": message.sender_sub,
        "recipient_sub": message.recipient_sub,
        "conversation_type": message.conversation_type,
        "created_at": iso_utc(message.created_at),
    }
    if message.conversation_type == "group":
        payload["group_id"] = message.group_id
    if message.deleted_at is not None:
        payload["deleted"] = True
    else:
        payload["deleted"] = False
        payload["content"] = message.content
        payload["content_type"] = message.content_type
        payload["forwarded"] = message.forwarded
        if message.attachment_name is not None:
            payload["attachment"] = {
                "name": message.attachment_name,
                "size": message.attachment_size,
                "mime": message.attachment_mime,
                "url": message.attachment_url,
            }
        if message.edited_at is not None:
            payload["edited_at"] = iso_utc(message.edited_at)
        if message.reply_to_id is not None and reply is not None:
            payload["reply_to"] = reply_payload(reply)
        payload["mentions"] = mentions if mentions is not None else []
    return payload


def reply_payload(target: Message) -> dict[str, Any]:
    return {
        "id": target.id,
        "sender_sub": target.sender_sub,
        "content": None if target.deleted_at is not None else target.content[:100],
        "deleted": target.deleted_at is not None,
        "content_type": target.content_type,
    }


async def validate_reply(
    db: AsyncSession,
    me_sub: str,
    reply_to_id: int,
    *,
    other_sub: str | None = None,
    group_id: int | None = None,
) -> Message:
    target = await db.get(Message, reply_to_id)
    if target is None:
        raise HTTPException(status_code=404, detail="replied message not found")
    if group_id is not None:
        if target.conversation_type != "group" or target.group_id != group_id:
            raise HTTPException(status_code=404, detail="replied message not in group")
    else:
        assert other_sub is not None
        lo, hi = pair_key(me_sub, other_sub)
        if target.conversation_type != "dm" or (
            target.participant_lo,
            target.participant_hi,
        ) != (lo, hi):
            raise HTTPException(
                status_code=404, detail="replied message not in conversation"
            )
    return target


async def validate_mentions(
    db: AsyncSession,
    mentions: list[str],
    *,
    other_sub: str | None = None,
    group_id: int | None = None,
) -> list[str]:
    if not mentions:
        return []
    if len(mentions) > MAX_MENTIONS:
        raise HTTPException(status_code=422, detail=f"at most {MAX_MENTIONS} mentions")
    if group_id is not None:
        for sub in mentions:
            if await group_membership(db, group_id, sub) is None:
                raise HTTPException(status_code=422, detail="mention must be a group member")
    else:
        assert other_sub is not None
        if set(mentions) - {other_sub}:
            raise HTTPException(status_code=422, detail="mention must be your chat partner")
    return list(dict.fromkeys(mentions))


async def resolve_attachment(
    db: AsyncSession,
    sender_sub: str,
    content_type: str,
    attachment: dict[str, Any] | None,
) -> dict[str, Any]:
    if content_type == "text":
        if attachment is not None:
            raise HTTPException(
                status_code=422, detail="text messages cannot have attachments"
            )
        return {}
    if attachment is None:
        raise HTTPException(status_code=422, detail="attachment required")
    url = attachment.get("url")
    prefix = "/api/uploads/"
    if not isinstance(url, str) or not url.startswith(prefix):
        raise HTTPException(status_code=422, detail="invalid attachment url")
    upload = await get_upload(db, url[len(prefix) :])
    if upload.owner_sub != sender_sub:
        raise HTTPException(status_code=403, detail="attachment must belong to you")
    return {
        "attachment_name": upload.original_name,
        "attachment_size": upload.size,
        "attachment_mime": upload.mime,
        "attachment_url": url,
    }


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
    db: AsyncSession,
    sender_sub: str,
    recipient_sub: str,
    content: str,
    *,
    content_type: str = "text",
    attachment: dict[str, Any] | None = None,
    reply_to_id: int | None = None,
    mentions: list[str] | None = None,
) -> Message:
    if sender_sub == recipient_sub:
        raise HTTPException(status_code=400, detail="cannot message yourself")
    if await db.get(User, recipient_sub) is None:
        raise HTTPException(status_code=404, detail="user not found")
    if not await are_friends(db, sender_sub, recipient_sub):
        raise HTTPException(status_code=403, detail="not friends")
    if reply_to_id is not None:
        await validate_reply(db, sender_sub, reply_to_id, other_sub=recipient_sub)
    mention_subs = await validate_mentions(db, mentions or [], other_sub=recipient_sub)
    attachment_fields = await resolve_attachment(
        db, sender_sub, content_type, attachment
    )
    lo, hi = pair_key(sender_sub, recipient_sub)
    message = Message(
        sender_sub=sender_sub,
        recipient_sub=recipient_sub,
        participant_lo=lo,
        participant_hi=hi,
        content=content,
        content_type=content_type,
        reply_to_id=reply_to_id,
        **attachment_fields,
    )
    db.add(message)
    await db.flush()
    for sub in mention_subs:
        db.add(MessageMention(message_id=message.id, user_sub=sub))
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
    dm_summaries = await _dm_conversation_summaries(db, me_sub)
    group_summaries = await _group_conversation_summaries(db, me_sub)
    summaries = [*dm_summaries, *group_summaries]
    settings = await conversation_settings_for(db, me_sub)
    for item in summaries:
        if item["peer"] is not None:
            kind = "dm"
            key = dm_key(me_sub, item["peer"]["sub"])
        else:
            kind = "group"
            key = str(item["group"]["id"])
        row = settings.get((kind, key))
        item["pinned"] = row.pinned if row is not None else False
        item["muted"] = row.muted if row is not None else False
    summaries.sort(
        key=lambda item: (
            0 if item["pinned"] else 1,
            -(
                item["last_message"]["id"]
                if item["last_message"] is not None
                else -1
            ),
        ),
    )
    return summaries


async def set_conversation_setting(
    db: AsyncSession,
    me_sub: str,
    kind: str,
    key: str,
    pinned: bool | None,
    muted: bool | None,
) -> dict[str, Any]:
    if kind not in {"dm", "group"}:
        raise HTTPException(status_code=422, detail="invalid kind")
    if pinned is None and muted is None:
        raise HTTPException(status_code=422, detail="pinned or muted is required")
    if kind == "dm":
        parts = key.split(":", 1)
        if len(parts) != 2 or parts[0] == parts[1]:
            raise HTTPException(status_code=422, detail="invalid dm key")
        if me_sub not in parts:
            raise HTTPException(status_code=404, detail="conversation not found")
        if dm_key(parts[0], parts[1]) != key:
            raise HTTPException(status_code=422, detail="invalid dm key")
    else:
        if not key.isdigit():
            raise HTTPException(status_code=422, detail="invalid group key")
        if await group_membership(db, int(key), me_sub) is None:
            raise HTTPException(status_code=404, detail="group not found")
    row = await db.get(UserConversationSetting, (me_sub, kind, key))
    if row is None:
        row = UserConversationSetting(
            user_sub=me_sub, kind=kind, key=key, pinned=False, muted=False
        )
        db.add(row)
    if pinned is not None:
        row.pinned = pinned
    if muted is not None:
        row.muted = muted
    await db.commit()
    await db.refresh(row)
    return {"kind": kind, "key": key, "pinned": row.pinned, "muted": row.muted}


async def conversation_settings_for(
    db: AsyncSession, me_sub: str
) -> dict[tuple[str, str], UserConversationSetting]:
    rows = (
        await db.execute(
            select(UserConversationSetting).where(
                UserConversationSetting.user_sub == me_sub
            )
        )
    ).scalars().all()
    return {(row.kind, row.key): row for row in rows}


async def _dm_conversation_summaries(
    db: AsyncSession, me_sub: str
) -> list[dict[str, Any]]:
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
                "group": None,
                "last_message": message_payload(last) if last is not None else None,
                "unread_count": (
                    unread_by_peer.get(friend_sub, 0) if friend_sub is not None else 0
                ),
                "last_read_id": cursor.last_read_message_id if cursor is not None else 0,
            }
        )
    return summaries


async def _group_conversation_summaries(
    db: AsyncSession, me_sub: str
) -> list[dict[str, Any]]:
    group_ids = (
        await db.execute(
            select(GroupMember.group_id).where(GroupMember.user_sub == me_sub)
        )
    ).scalars().all()
    if not group_ids:
        return []
    groups = (
        await db.execute(select(Group).where(Group.id.in_(list(group_ids))))
    ).scalars().all()
    read_rows = (
        await db.execute(
            select(GroupRead).where(
                GroupRead.user_sub == me_sub, GroupRead.group_id.in_(list(group_ids))
            )
        )
    ).scalars().all()
    cursors = {row.group_id: row.last_read_message_id for row in read_rows}
    messages = (
        await db.execute(
            select(Message)
            .where(
                Message.conversation_type == "group",
                Message.group_id.in_(list(group_ids)),
            )
            .order_by(Message.id.desc())
        )
    ).scalars().all()
    last_by_group: dict[int, Message] = {}
    unread_by_group: dict[int, int] = {}
    for message in messages:
        group_id = message.group_id
        if group_id is None:
            continue
        last_by_group.setdefault(group_id, message)
        if message.sender_sub != me_sub and message.id > cursors.get(group_id, 0):
            unread_by_group[group_id] = unread_by_group.get(group_id, 0) + 1
    summaries: list[dict[str, Any]] = []
    for group in groups:
        last = last_by_group.get(group.id)
        summaries.append(
            {
                "peer": None,
                "group": {
                    "id": group.id,
                    "name": group.name,
                    "owner_sub": group.owner_sub,
                    "member_count": await _group_member_count(db, group.id),
                    "avatar_url": group.avatar_url,
                },
                "last_message": message_payload(last) if last is not None else None,
                "unread_count": unread_by_group.get(group.id, 0),
                "last_read_id": cursors.get(group.id, 0),
            }
        )
    return summaries


async def _group_member_count(db: AsyncSession, group_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(GroupMember).where(GroupMember.group_id == group_id)
    )
    return int(result.scalar_one())


async def send_group_message(
    db: AsyncSession,
    sender_sub: str,
    group_id: int,
    content: str,
    *,
    content_type: str = "text",
    attachment: dict[str, Any] | None = None,
    reply_to_id: int | None = None,
    mentions: list[str] | None = None,
) -> Message:
    member_row = await group_membership(db, group_id, sender_sub)
    if member_row is None:
        raise HTTPException(status_code=403, detail="not a group member")
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    if reply_to_id is not None:
        await validate_reply(db, sender_sub, reply_to_id, group_id=group_id)
    mention_subs = await validate_mentions(db, mentions or [], group_id=group_id)
    attachment_fields = await resolve_attachment(
        db, sender_sub, content_type, attachment
    )
    marker = f"{GROUP_RECIPIENT_PREFIX}{group_id}"
    message = Message(
        sender_sub=sender_sub,
        recipient_sub=marker,
        participant_lo=marker,
        participant_hi=f"{marker}:end",
        content=content,
        conversation_type="group",
        group_id=group_id,
        content_type=content_type,
        reply_to_id=reply_to_id,
        **attachment_fields,
    )
    db.add(message)
    await db.flush()
    for sub in mention_subs:
        db.add(MessageMention(message_id=message.id, user_sub=sub))
    await _advance_group_read(db, sender_sub, group_id, message.id)
    await db.commit()
    await db.refresh(message)
    return message


async def _advance_group_read(
    db: AsyncSession, user_sub: str, group_id: int, message_id: int
) -> None:
    row = await db.get(GroupRead, (user_sub, group_id))
    if row is None:
        db.add(
            GroupRead(
                user_sub=user_sub, group_id=group_id, last_read_message_id=message_id
            )
        )
    elif message_id > row.last_read_message_id:
        row.last_read_message_id = message_id


async def group_history(
    db: AsyncSession,
    me_sub: str,
    group_id: int,
    *,
    before: int | None = None,
    limit: int = HISTORY_DEFAULT_LIMIT,
) -> tuple[list[Message], int | None]:
    member_row = await group_membership(db, group_id, me_sub)
    if member_row is None:
        raise HTTPException(status_code=404, detail="group not found")
    stmt = (
        select(Message)
        .where(Message.conversation_type == "group", Message.group_id == group_id)
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


async def mark_group_read(
    db: AsyncSession, me_sub: str, group_id: int, last_read_id: int
) -> None:
    member_row = await group_membership(db, group_id, me_sub)
    if member_row is None:
        raise HTTPException(status_code=404, detail="group not found")
    message = await db.get(Message, last_read_id)
    if (
        message is None
        or message.conversation_type != "group"
        or message.group_id != group_id
    ):
        raise HTTPException(status_code=404, detail="message not found in group")
    await _advance_group_read(db, me_sub, group_id, last_read_id)
    await db.commit()


async def _can_view(db: AsyncSession, me_sub: str, message: Message) -> bool:
    if message.conversation_type == "dm":
        return me_sub in (message.participant_lo, message.participant_hi)
    return message.group_id is not None and (
        await group_membership(db, message.group_id, me_sub) is not None
    )


async def forward_message(
    db: AsyncSession,
    me_sub: str,
    message_id: int,
    *,
    to_sub: str | None = None,
    group_id: int | None = None,
) -> Message:
    source = await db.get(Message, message_id)
    if source is None or not await _can_view(db, me_sub, source):
        raise HTTPException(status_code=404, detail="message not found")
    if source.deleted_at is not None:
        raise HTTPException(status_code=409, detail="cannot forward deleted message")
    attachment_fields: dict[str, Any] = {}
    if source.attachment_url is not None:
        attachment_fields = {
            "attachment_name": source.attachment_name,
            "attachment_size": source.attachment_size,
            "attachment_mime": source.attachment_mime,
            "attachment_url": source.attachment_url,
        }
    if group_id is not None:
        member_row = await group_membership(db, group_id, me_sub)
        if member_row is None:
            raise HTTPException(status_code=403, detail="not a group member")
        marker = f"{GROUP_RECIPIENT_PREFIX}{group_id}"
        message = Message(
            sender_sub=me_sub,
            recipient_sub=marker,
            participant_lo=marker,
            participant_hi=f"{marker}:end",
            content=source.content,
            conversation_type="group",
            group_id=group_id,
            content_type=source.content_type,
            forwarded=True,
            **attachment_fields,
        )
        db.add(message)
        await db.flush()
        await _advance_group_read(db, me_sub, group_id, message.id)
        await db.commit()
        await db.refresh(message)
        return message
    assert to_sub is not None
    if me_sub == to_sub:
        raise HTTPException(status_code=400, detail="cannot forward to yourself")
    if await db.get(User, to_sub) is None:
        raise HTTPException(status_code=404, detail="user not found")
    if not await are_friends(db, me_sub, to_sub):
        raise HTTPException(status_code=403, detail="not friends")
    lo, hi = pair_key(me_sub, to_sub)
    message = Message(
        sender_sub=me_sub,
        recipient_sub=to_sub,
        participant_lo=lo,
        participant_hi=hi,
        content=source.content,
        content_type=source.content_type,
        forwarded=True,
        **attachment_fields,
    )
    db.add(message)
    await db.flush()
    await _advance_read(db, me_sub, lo, hi, message.id)
    await db.commit()
    await db.refresh(message)
    return message


async def mentions_for(
    db: AsyncSession, message_ids: list[int]
) -> dict[int, list[str]]:
    if not message_ids:
        return {}
    rows = (
        await db.execute(
            select(MessageMention).where(MessageMention.message_id.in_(message_ids))
        )
    ).scalars().all()
    result: dict[int, list[str]] = {}
    for row in rows:
        result.setdefault(row.message_id, []).append(row.user_sub)
    return result


async def set_star(
    db: AsyncSession, me_sub: str, message_id: int, *, starred: bool
) -> dict[str, Any]:
    message = await db.get(Message, message_id)
    if message is None or not await _can_view(db, me_sub, message):
        raise HTTPException(status_code=404, detail="message not found")
    row = await db.get(UserStar, (me_sub, message_id))
    if starred and row is None:
        db.add(UserStar(user_sub=me_sub, message_id=message_id))
        await db.commit()
    elif not starred and row is not None:
        await db.delete(row)
        await db.commit()
    return {"message_id": message_id, "starred": starred}


async def starred_for(
    db: AsyncSession, viewer_sub: str, message_ids: list[int]
) -> set[int]:
    if not message_ids:
        return set()
    rows = (
        await db.execute(
            select(UserStar.message_id).where(
                UserStar.user_sub == viewer_sub,
                UserStar.message_id.in_(message_ids),
            )
        )
    ).scalars().all()
    return set(rows)


async def starred_messages(
    db: AsyncSession,
    me_sub: str,
    *,
    cursor: int | None = None,
    limit: int = 20,
) -> tuple[list[dict[str, Any]], int | None]:
    stmt = (
        select(UserStar)
        .where(UserStar.user_sub == me_sub)
        .order_by(UserStar.message_id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(UserStar.message_id < cursor)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    page = list(rows[:limit])
    message_ids = [row.message_id for row in page]
    messages = (
        await db.execute(select(Message).where(Message.id.in_(message_ids)))
    ).scalars().all()
    by_id = {message.id: message for message in messages}
    items: list[dict[str, Any]] = []
    for row in page:
        message = by_id.get(row.message_id)
        if message is None:
            continue
        conversation: dict[str, Any]
        if message.conversation_type == "group":
            group = (
                await db.get(Group, message.group_id)
                if message.group_id is not None
                else None
            )
            conversation = {
                "type": "group",
                "group_id": message.group_id,
                "group_name": group.name if group is not None else None,
                "peer_sub": None,
                "peer_name": None,
            }
        else:
            peer = (
                message.sender_sub
                if message.sender_sub != me_sub
                else message.recipient_sub
            )
            peer_user = await db.get(User, peer)
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
                "id": message.id,
                "sender_sub": message.sender_sub,
                "conversation": conversation,
                "content": (
                    None if message.deleted_at is not None else message.content[:200]
                ),
                "content_type": message.content_type,
                "deleted": message.deleted_at is not None,
                "created_at": iso_utc(message.created_at),
            }
        )
    next_before = page[-1].message_id if has_more and page else None
    return items, next_before


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


def clean_emoji(value: str) -> str:
    stripped = value.strip()
    if not stripped or len(stripped) > EMOJI_MAX_LENGTH:
        raise ValueError(f"emoji must be 1-{EMOJI_MAX_LENGTH} characters")
    for char in stripped:
        if char.isspace():
            raise ValueError("emoji must not contain whitespace")
        category = unicodedata.category(char)
        if category in {"Cc", "Cf"} and char != "\u200d":
            raise ValueError("emoji must not contain control characters")
    return stripped


async def set_reaction(
    db: AsyncSession,
    me_sub: str,
    other_sub: str,
    message_id: int,
    emoji: str,
    *,
    add: bool,
) -> dict[str, Any]:
    lo, hi = pair_key(me_sub, other_sub)
    message = await db.get(Message, message_id)
    if message is None or (message.participant_lo, message.participant_hi) != (lo, hi):
        raise HTTPException(status_code=404, detail="message not found in conversation")
    if message.deleted_at is not None:
        raise HTTPException(status_code=409, detail="message deleted")
    existing = await db.get(Reaction, (message_id, me_sub, emoji))
    if add and existing is None:
        db.add(Reaction(message_id=message_id, user_sub=me_sub, emoji=emoji))
        await db.commit()
    elif not add and existing is not None:
        await db.delete(existing)
        await db.commit()
    count = await _reaction_count(db, message_id, emoji)
    return {
        "message_id": message_id,
        "emoji": emoji,
        "action": "added" if add else "removed",
        "count": count,
    }


async def _reaction_count(db: AsyncSession, message_id: int, emoji: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Reaction)
        .where(Reaction.message_id == message_id, Reaction.emoji == emoji)
    )
    return int(result.scalar_one())


async def reactions_for(
    db: AsyncSession, message_ids: list[int], viewer_sub: str
) -> dict[int, dict[str, Any]]:
    if not message_ids:
        return {}
    rows = (
        await db.execute(select(Reaction).where(Reaction.message_id.in_(message_ids)))
    ).scalars().all()
    counts: dict[int, dict[str, int]] = {}
    mine: dict[int, set[str]] = {}
    for row in rows:
        counts.setdefault(row.message_id, {})
        counts[row.message_id][row.emoji] = counts[row.message_id].get(row.emoji, 0) + 1
        if row.user_sub == viewer_sub:
            mine.setdefault(row.message_id, set()).add(row.emoji)
    result: dict[int, dict[str, Any]] = {}
    for message_id in message_ids:
        per_emoji = counts.get(message_id, {})
        result[message_id] = {
            "reactions": [
                {"emoji": emoji, "count": count}
                for emoji, count in sorted(per_emoji.items())
            ],
            "my_reactions": sorted(mine.get(message_id, set())),
        }
    return result
