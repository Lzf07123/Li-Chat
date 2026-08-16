from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.groups import service
from app.models import User
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
