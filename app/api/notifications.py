from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.models import Notification, User
from app.notifications import service
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/me", tags=["notifications"])


class ActorOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class NotificationGroupOut(BaseModel):
    id: int
    name: str | None = None


class NotificationOut(BaseModel):
    id: int
    type: str
    actor: ActorOut | None = None
    group: NotificationGroupOut | None = None
    payload: dict[str, object] = {}
    read: bool
    created_at: str


class NotificationsOut(BaseModel):
    notifications: list[NotificationOut]
    next_cursor: int | None
    unread_count: int


class StatusOut(BaseModel):
    status: str


async def push_notification(
    request: Request, db: AsyncSession, notification: Notification
) -> None:
    actor = (
        await db.get(User, notification.actor_sub)
        if notification.actor_sub
        else None
    )
    payload = service.notification_payload(notification, actor)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    await manager.send_to(
        notification.user_sub,
        {"type": "notification", "notification": payload},
    )


@router.get("/notifications", response_model=NotificationsOut)
async def notifications_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> NotificationsOut:
    items, next_cursor, unread = await service.list_for(
        db, user.sub, cursor=cursor, limit=limit
    )
    return NotificationsOut(
        notifications=items,
        next_cursor=next_cursor,
        unread_count=unread,
    )


@router.post("/notifications/read", response_model=StatusOut)
async def notifications_mark_read(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    await service.mark_all_read(db, user.sub)
    return StatusOut(status="ok")
