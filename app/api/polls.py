from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_action_rate, require_csrf
from app.db import get_db
from app.groups import service as groups_service
from app.models import User
from app.polls import service
from app.timeutil import iso_utc, utcnow
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/groups", tags=["polls"])


class PollOptionOut(BaseModel):
    index: int
    text: str
    count: int


class PollOut(BaseModel):
    id: int
    question: str
    options: list[PollOptionOut]
    multiple: bool
    closed: bool
    total_votes: int
    my_votes: list[int]
    creator_sub: str
    created_at: str


class VoteIn(BaseModel):
    option_indexes: list[int] = Field(min_length=1, max_length=service.POLL_OPTIONS_MAX)


async def _broadcast_poll(
    request: Request,
    db: AsyncSession,
    group_id: int,
    poll_id: int,
    event: str,
    payload: dict[str, object],
    by_sub: str,
) -> None:
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    frame = {
        "type": "poll_event",
        "event": event,
        "group_id": group_id,
        "poll_id": poll_id,
        "poll": payload,
        "by_sub": by_sub,
        "at": iso_utc(utcnow()),
    }
    for sub in await groups_service.member_subs(db, group_id):
        await manager.send_to(sub, frame)


@router.put("/{group_id}/polls/{poll_id}/vote", response_model=PollOut)
async def vote_poll(
    request: Request,
    group_id: int,
    poll_id: int,
    body: VoteIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
    _rate: Annotated[None, Depends(require_action_rate)],
) -> PollOut:
    poll = await service.vote(db, user.sub, group_id, poll_id, body.option_indexes)
    payload = await service.poll_payload(db, poll, user.sub)
    await _broadcast_poll(request, db, group_id, poll_id, "voted", payload, user.sub)
    return PollOut(**payload)


@router.post("/{group_id}/polls/{poll_id}/close", response_model=PollOut)
async def close_poll(
    request: Request,
    group_id: int,
    poll_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> PollOut:
    poll = await service.close_poll(db, user.sub, group_id, poll_id)
    payload = await service.poll_payload(db, poll, user.sub)
    await _broadcast_poll(request, db, group_id, poll_id, "closed", payload, user.sub)
    return PollOut(**payload)
