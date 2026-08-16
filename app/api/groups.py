from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.messages import (
    ForwardIn,
    MessageIn,
    MessageOut,
    MessagePageOut,
    ReactionIn,
    ReactionOut,
    ReadIn,
    ReadOut,
)
from app.api.notifications import push_notification
from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.groups import service
from app.messages import service as messages_service
from app.models import Group, GroupRead, Message, Poll, User
from app.notifications.service import create as create_notification
from app.polls import service as polls_service
from app.timeutil import iso_utc, utcnow
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/groups", tags=["groups"])


class UserOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class MemberOut(BaseModel):
    user: UserOut
    role: str
    muted: bool = False
    joined_at: str


class GroupOut(BaseModel):
    id: int
    name: str
    owner_sub: str
    announcement: str | None = None
    announcement_updated_at: str | None = None
    avatar_url: str | None = None
    created_at: str
    members: list[MemberOut]


class GroupFileOut(BaseModel):
    message_id: int
    sender_sub: str
    name: str | None = None
    size: int | None = None
    mime: str | None = None
    url: str | None = None
    created_at: str


class GroupFilesOut(BaseModel):
    files: list[GroupFileOut]
    next_before: int | None


class ReaderOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class GroupReadsOut(BaseModel):
    read_count: int
    total_members: int
    readers: list[ReaderOut]


class HideOut(BaseModel):
    status: str


class AnnouncementIn(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) > service.GROUP_ANNOUNCEMENT_MAX:
            raise ValueError(
                f"announcement must be at most {service.GROUP_ANNOUNCEMENT_MAX} characters"
            )
        return stripped


class AvatarIn(BaseModel):
    url: str


class GroupsOut(BaseModel):
    groups: list[GroupOut]


class GroupIn(BaseModel):
    name: str
    member_subs: list[str] = []

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        try:
            return service.clean_name(value)
        except ValueError as error:
            raise ValueError(str(error)) from error

    @field_validator("member_subs")
    @classmethod
    def _validate_subs(cls, value: list[str]) -> list[str]:
        if len(value) > service.INVITE_BATCH_MAX:
            raise ValueError(
                f"at most {service.INVITE_BATCH_MAX} invitees per request"
            )
        return value


class RenameIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        try:
            return service.clean_name(value)
        except ValueError as error:
            raise ValueError(str(error)) from error


class MembersIn(BaseModel):
    member_subs: list[str]

    @field_validator("member_subs")
    @classmethod
    def _validate_subs(cls, value: list[str]) -> list[str]:
        if len(value) > service.INVITE_BATCH_MAX:
            raise ValueError(
                f"at most {service.INVITE_BATCH_MAX} invitees per request"
            )
        return value


class RoleIn(BaseModel):
    role: Literal["admin", "member"]


class MuteIn(BaseModel):
    muted: bool


class TransferIn(BaseModel):
    new_owner_sub: str


class StatusOut(BaseModel):
    status: str


async def _broadcast(
    request: Request,
    db: AsyncSession,
    group_id: int,
    event: str,
    group: dict[str, Any],
    by_sub: str,
) -> None:
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    payload = {
        "type": "group_event",
        "event": event,
        "group_id": group_id,
        "group": group,
        "by_sub": by_sub,
        "at": iso_utc(utcnow()),
    }
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, payload)


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    request: Request,
    body: GroupIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> GroupOut:
    group = await service.create_group(db, user.sub, body.name, body.member_subs)
    await _broadcast(request, db, group["id"], "created", group, user.sub)
    return GroupOut.model_validate(group)


@router.get("", response_model=GroupsOut)
async def groups_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupsOut:
    return GroupsOut(groups=await service.list_groups(db, user.sub))


@router.get("/{group_id}", response_model=GroupOut)
async def group_detail(
    group_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupOut:
    return GroupOut.model_validate(await service.get_group(db, user.sub, group_id))


@router.get("/{group_id}/files", response_model=GroupFilesOut)
async def group_files(
    group_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> GroupFilesOut:
    files, next_before = await messages_service.group_files(
        db, user.sub, group_id, before=before, limit=limit
    )
    return GroupFilesOut(files=files, next_before=next_before)


@router.get("/{group_id}/messages/{message_id}/reads", response_model=GroupReadsOut)
async def group_message_reads(
    group_id: int,
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupReadsOut:
    readers, read_count, total_members = (
        await messages_service.group_message_readers(
            db, user.sub, group_id, message_id
        )
    )
    return GroupReadsOut(
        read_count=read_count,
        total_members=total_members,
        readers=readers,
    )


@router.patch("/{group_id}", response_model=GroupOut)
async def rename_group(
    request: Request,
    group_id: int,
    body: RenameIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> GroupOut:
    group = await service.rename_group(db, user.sub, group_id, body.name)
    await _broadcast(request, db, group_id, "renamed", group, user.sub)
    return GroupOut.model_validate(group)


@router.post("/{group_id}/members", response_model=GroupOut)
async def add_members(
    request: Request,
    group_id: int,
    body: MembersIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> GroupOut:
    group = await service.add_members(db, user.sub, group_id, body.member_subs)
    await _broadcast(request, db, group_id, "member_joined", group, user.sub)
    return GroupOut.model_validate(group)


@router.delete("/{group_id}/members/{target_sub}", response_model=StatusOut)
async def remove_member(
    request: Request,
    group_id: int,
    target_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    await service.remove_member(db, user.sub, group_id, target_sub)
    group = await service.get_group(db, user.sub, group_id)
    await _broadcast(request, db, group_id, "member_removed", group, user.sub)
    return StatusOut(status="removed")


@router.patch("/{group_id}/members/{target_sub}", response_model=StatusOut)
async def set_member_role(
    request: Request,
    group_id: int,
    target_sub: str,
    body: RoleIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    await service.set_member_role(db, user.sub, group_id, target_sub, body.role)
    group = await service.get_group(db, user.sub, group_id)
    await _broadcast(request, db, group_id, "role_changed", group, user.sub)
    notification = await create_notification(
        db,
        target_sub,
        "role_changed",
        actor_sub=user.sub,
        group_id=group_id,
        payload={"group_name": group["name"], "role": body.role},
    )
    await push_notification(request, db, notification)
    return StatusOut(status=body.role)


@router.patch("/{group_id}/members/{target_sub}/mute", response_model=StatusOut)
async def set_member_mute(
    request: Request,
    group_id: int,
    target_sub: str,
    body: MuteIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    await service.set_member_mute(db, user.sub, group_id, target_sub, body.muted)
    group = await service.get_group(db, user.sub, group_id)
    await _broadcast(request, db, group_id, "member_muted", group, user.sub)
    notification = await create_notification(
        db,
        target_sub,
        "muted" if body.muted else "unmuted",
        actor_sub=user.sub,
        group_id=group_id,
        payload={"group_name": group["name"]},
    )
    await push_notification(request, db, notification)
    return StatusOut(status="muted" if body.muted else "unmuted")


@router.post("/{group_id}/leave", response_model=StatusOut)
async def leave_group(
    request: Request,
    group_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    group = await service.get_group(db, user.sub, group_id)
    await service.leave_group(db, user.sub, group_id)
    await _broadcast(request, db, group_id, "member_left", group, user.sub)
    return StatusOut(status="left")


@router.post("/{group_id}/dissolve", response_model=StatusOut)
async def dissolve_group(
    request: Request,
    group_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    payload, member_subs = await service.dissolve_group(db, user.sub, group_id)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {
        "type": "group_event",
        "event": "dissolved",
        "group_id": group_id,
        "group": payload,
        "by_sub": user.sub,
        "at": iso_utc(utcnow()),
    }
    for sub in member_subs:
        await manager.send_to(sub, event)
        notification = await create_notification(
            db,
            sub,
            "group_dissolved",
            actor_sub=user.sub,
            group_id=group_id,
            payload={"group_name": payload["name"]},
        )
        await push_notification(request, db, notification)
    return StatusOut(status="dissolved")


@router.post("/{group_id}/transfer", response_model=StatusOut)
async def transfer_ownership(
    request: Request,
    group_id: int,
    body: TransferIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    await service.transfer_ownership(db, user.sub, group_id, body.new_owner_sub)
    group = await service.get_group(db, user.sub, group_id)
    await _broadcast(request, db, group_id, "owner_changed", group, user.sub)
    return StatusOut(status="transferred")


@router.patch("/{group_id}/announcement", response_model=GroupOut)
async def set_announcement(
    request: Request,
    group_id: int,
    body: AnnouncementIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> GroupOut:
    group = await service.set_announcement(db, user.sub, group_id, body.text)
    await _broadcast(request, db, group_id, "announcement_updated", group, user.sub)
    return GroupOut.model_validate(group)


@router.post("/{group_id}/avatar", response_model=GroupOut)
async def set_group_avatar(
    request: Request,
    group_id: int,
    body: AvatarIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> GroupOut:
    group = await service.set_avatar(db, user.sub, group_id, body.url)
    await _broadcast(request, db, group_id, "avatar_updated", group, user.sub)
    return GroupOut.model_validate(group)


@router.post("/{group_id}/messages", response_model=MessageOut, status_code=201)
async def send_group_message(
    request: Request,
    group_id: int,
    body: MessageIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await messages_service.send_group_message(
        db,
        user.sub,
        group_id,
        body.content,
        content_type=body.content_type,
        attachment=body.attachment.model_dump() if body.attachment else None,
        reply_to_id=body.reply_to_id,
        mentions=body.mentions,
        poll=body.poll.model_dump() if body.poll else None,
    )
    mention_subs = list(dict.fromkeys(body.mentions))
    reply = (
        await db.get(Message, message.reply_to_id)
        if message.reply_to_id is not None
        else None
    )
    payload = messages_service.message_payload(message, reply, mention_subs)
    if message.poll_id is not None:
        poll_row = await db.get(Poll, message.poll_id)
        if poll_row is not None:
            payload["poll"] = await polls_service.poll_payload(db, poll_row, user.sub)
    if message.sender_sub == user.sub:
        read_rows = (
            await db.execute(
                select(GroupRead).where(
                    GroupRead.group_id == group_id,
                    GroupRead.last_read_message_id >= message.id,
                )
            )
        ).scalars().all()
        payload["read_count"] = len(read_rows)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message", "message": payload}
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, event)
    group_row = await db.get(Group, group_id)
    for mention_sub in set(mention_subs) - {user.sub}:
        notification = await create_notification(
            db,
            mention_sub,
            "mention",
            actor_sub=user.sub,
            group_id=group_id,
            payload={
                "group_name": group_row.name if group_row else None,
                "message_id": message.id,
            },
        )
        await push_notification(request, db, notification)
    return MessageOut(**payload)


@router.get("/{group_id}/messages", response_model=MessagePageOut)
async def group_history(
    group_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=messages_service.HISTORY_MAX_LIMIT)] = (
        messages_service.HISTORY_DEFAULT_LIMIT
    ),
) -> MessagePageOut:
    rows, next_before = await messages_service.group_history(
        db, user.sub, group_id, before=before, limit=limit
    )
    reaction_map = await messages_service.reactions_for(
        db, [item.id for item in rows], user.sub
    )
    mentions = await messages_service.mentions_for(db, [item.id for item in rows])
    starred_ids = await messages_service.starred_for(
        db, user.sub, [item.id for item in rows]
    )
    poll_ids = [item.poll_id for item in rows if item.poll_id is not None]
    polls_map: dict[int, dict[str, Any]] = {}
    for poll_id in set(poll_ids):
        poll_row = await db.get(Poll, poll_id)
        if poll_row is not None:
            polls_map[poll_id] = await polls_service.poll_payload(db, poll_row, user.sub)
    read_rows = (
        await db.execute(select(GroupRead).where(GroupRead.group_id == group_id))
    ).scalars().all()
    reply_ids = [item.reply_to_id for item in rows if item.reply_to_id is not None]
    replies: dict[int, Message] = {}
    if reply_ids:
        targets = (
            await db.execute(
                select(Message).where(Message.id.in_(reply_ids))
            )
        ).scalars().all()
        replies = {target.id: target for target in targets}
    messages: list[MessageOut] = []
    for item in rows:
        reply = (
            replies.get(item.reply_to_id)
            if item.reply_to_id is not None
            else None
        )
        data = messages_service.message_payload(item, reply)
        if item.poll_id is not None and item.poll_id in polls_map:
            data["poll"] = polls_map[item.poll_id]
        if item.sender_sub == user.sub:
            data["read_count"] = sum(
                1
                for row in read_rows
                if row.last_read_message_id >= item.id
            )
        if "mentions" in data:
            data["mentions"] = mentions.get(item.id, [])
        aggregate = reaction_map.get(item.id, {})
        messages.append(
            MessageOut(
                **data,
                reactions=aggregate.get("reactions", []),
                my_reactions=aggregate.get("my_reactions", []),
                starred=item.id in starred_ids,
            )
        )
    return MessagePageOut(messages=messages, next_before=next_before)


@router.post("/{group_id}/read", response_model=ReadOut)
async def mark_group_read(
    request: Request,
    group_id: int,
    body: ReadIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ReadOut:
    await messages_service.mark_group_read(db, user.sub, group_id, body.last_read_id)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {
        "type": "read_receipt",
        "by_sub": user.sub,
        "group_id": group_id,
        "last_read_id": body.last_read_id,
    }
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, event)
    return ReadOut(status="ok", last_read_id=body.last_read_id)


@router.post("/{group_id}/forward", response_model=MessageOut, status_code=201)
async def forward_group_message(
    request: Request,
    group_id: int,
    body: ForwardIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await messages_service.forward_message(
        db, user.sub, body.message_id, group_id=group_id
    )
    payload = messages_service.message_payload(message)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message", "message": payload}
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, event)
    return MessageOut(**payload)


@router.patch("/{group_id}/messages/{message_id}", response_model=MessageOut)
async def edit_group_message(
    request: Request,
    group_id: int,
    message_id: int,
    body: MessageIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await messages_service.edit_group_message(
        db, user.sub, group_id, message_id, body.content
    )
    reply = (
        await db.get(Message, message.reply_to_id)
        if message.reply_to_id is not None
        else None
    )
    payload = messages_service.message_payload(message, reply)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message_edited", "message": payload}
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, event)
    return MessageOut(**payload)


@router.delete("/{group_id}/messages/{message_id}", response_model=MessageOut)
async def delete_group_message(
    request: Request,
    group_id: int,
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await messages_service.delete_group_message(
        db, user.sub, group_id, message_id
    )
    payload = messages_service.message_payload(message)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message_deleted", "message": payload}
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, event)
    return MessageOut(**payload)


@router.delete("/{group_id}/messages/{message_id}/me", response_model=HideOut)
async def hide_group_message(
    group_id: int,
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> HideOut:
    await messages_service.hide_message_for_self(
        db, user.sub, message_id, group_id=group_id
    )
    return HideOut(status="hidden")


@router.put(
    "/{group_id}/messages/{message_id}/reactions", response_model=ReactionOut
)
async def add_group_reaction(
    request: Request,
    group_id: int,
    message_id: int,
    body: ReactionIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ReactionOut:
    result = await messages_service.set_group_reaction(
        db, user.sub, group_id, message_id, body.emoji, add=True
    )
    await _broadcast_group_reaction(request, db, group_id, result, user.sub)
    return ReactionOut(**result)


@router.delete(
    "/{group_id}/messages/{message_id}/reactions", response_model=ReactionOut
)
async def remove_group_reaction(
    request: Request,
    group_id: int,
    message_id: int,
    emoji: Annotated[str, Query(min_length=1, max_length=16)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ReactionOut:
    try:
        cleaned = messages_service.clean_emoji(emoji)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    result = await messages_service.set_group_reaction(
        db, user.sub, group_id, message_id, cleaned, add=False
    )
    await _broadcast_group_reaction(request, db, group_id, result, user.sub)
    return ReactionOut(**result)


async def _broadcast_group_reaction(
    request: Request,
    db: AsyncSession,
    group_id: int,
    result: dict[str, Any],
    by_sub: str,
) -> None:
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {
        "type": "message_reaction",
        "message_id": result["message_id"],
        "emoji": result["emoji"],
        "action": result["action"],
        "count": result["count"],
        "by_sub": by_sub,
    }
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, event)
