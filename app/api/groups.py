from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.messages import MessageIn, MessageOut, MessagePageOut, ReadIn, ReadOut
from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.groups import service
from app.messages import service as messages_service
from app.models import Message, User
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
    joined_at: str


class GroupOut(BaseModel):
    id: int
    name: str
    owner_sub: str
    created_at: str
    members: list[MemberOut]


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
    return StatusOut(status=body.role)


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
    )
    reply = (
        await db.get(Message, message.reply_to_id)
        if message.reply_to_id is not None
        else None
    )
    payload = messages_service.message_payload(message, reply)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message", "message": payload}
    for sub in await service.member_subs(db, group_id):
        await manager.send_to(sub, event)
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
        aggregate = reaction_map.get(item.id, {})
        messages.append(
            MessageOut(
                **data,
                reactions=aggregate.get("reactions", []),
                my_reactions=aggregate.get("my_reactions", []),
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
