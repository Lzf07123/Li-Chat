from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.friends import service
from app.models import User
from app.timeutil import iso_utc
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/friends", tags=["friends"])


class ProfileOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class FriendRequestIn(BaseModel):
    to_sub: str


class FriendRequestOut(BaseModel):
    requester_sub: str
    addressee_sub: str
    status: str
    created_at: str


class IncomingRequestOut(BaseModel):
    requester: ProfileOut
    created_at: str


class OutgoingRequestOut(BaseModel):
    addressee: ProfileOut
    created_at: str


class RequestsOut(BaseModel):
    incoming: list[IncomingRequestOut]
    outgoing: list[OutgoingRequestOut]


def _manager(request: Request) -> ConnectionManager:
    return cast(ConnectionManager, request.app.state.ws_manager)


@router.get("/requests", response_model=RequestsOut)
async def requests_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestsOut:
    return RequestsOut.model_validate(await service.list_requests(db, user.sub))


@router.post("/requests", response_model=FriendRequestOut, status_code=201)
async def create_request(
    request: Request,
    body: FriendRequestIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> FriendRequestOut:
    friendship = await service.send_request(db, user.sub, body.to_sub)
    await _manager(request).send_to(
        friendship.addressee_sub,
        {
            "type": "friend_event",
            "event": "request_received",
            "by_sub": friendship.requester_sub,
            "at": iso_utc(friendship.created_at),
        },
    )
    return FriendRequestOut(
        requester_sub=friendship.requester_sub,
        addressee_sub=friendship.addressee_sub,
        status=friendship.status,
        created_at=iso_utc(friendship.created_at),
    )
