from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.friends import service
from app.models import User
from app.timeutil import iso_utc, utcnow
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/friends", tags=["friends"])


class ProfileOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class FriendPresenceOut(ProfileOut):
    online: bool
    last_seen_at: str | None = None
    bio: str | None = None


class FriendsPresenceOut(BaseModel):
    friends: list[FriendPresenceOut]


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


class FriendsOut(BaseModel):
    friends: list[ProfileOut]


class StatusOut(BaseModel):
    status: str


def _manager(request: Request) -> ConnectionManager:
    return cast(ConnectionManager, request.app.state.ws_manager)


@router.get("/requests", response_model=RequestsOut)
async def requests_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestsOut:
    return RequestsOut.model_validate(await service.list_requests(db, user.sub))


@router.get("/recommendations", response_model=FriendsOut)
async def recommendations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=service.RECOMMENDATION_MAX_LIMIT)] = (
        service.RECOMMENDATION_DEFAULT_LIMIT
    ),
) -> FriendsOut:
    return FriendsOut(friends=await service.recommend_friends(db, user.sub, limit=limit))


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


@router.get("", response_model=FriendsPresenceOut)
async def friends_list(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FriendsPresenceOut:
    manager = _manager(request)
    friends = await service.list_friends(db, user.sub)
    items: list[FriendPresenceOut] = []
    for friend in friends:
        sub = cast(str, friend["sub"])
        items.append(
            FriendPresenceOut(
                sub=sub,
                nickname=friend["nickname"],
                name=friend["name"],
                picture=friend["picture"],
                online=manager.has(sub),
                last_seen_at=friend["last_seen_at"],
                bio=friend["bio"],
            )
        )
    return FriendsPresenceOut(friends=items)


@router.post("/requests/{from_sub}/accept", response_model=StatusOut)
async def accept_request(
    request: Request,
    from_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    friendship = await service.accept_request(db, user.sub, from_sub)
    await _manager(request).send_to(
        friendship.requester_sub,
        {
            "type": "friend_event",
            "event": "request_accepted",
            "by_sub": friendship.addressee_sub,
            "at": iso_utc(friendship.updated_at),
        },
    )
    return StatusOut(status="accepted")


@router.post("/requests/{from_sub}/reject", response_model=StatusOut)
async def reject_request(
    request: Request,
    from_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    await service.reject_request(db, user.sub, from_sub)
    await _manager(request).send_to(
        from_sub,
        {
            "type": "friend_event",
            "event": "request_rejected",
            "by_sub": user.sub,
            "at": iso_utc(utcnow()),
        },
    )
    return StatusOut(status="rejected")


@router.delete("/{other_sub}", response_model=StatusOut)
async def remove_friend(
    request: Request,
    other_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    row = await service.remove_relationship(db, user.sub, other_sub)
    if row is None:
        raise HTTPException(status_code=404, detail="no relationship")
    await _manager(request).send_to(
        other_sub,
        {
            "type": "friend_event",
            "event": "friend_removed",
            "by_sub": user.sub,
            "at": iso_utc(utcnow()),
        },
    )
    return StatusOut(status="removed")
