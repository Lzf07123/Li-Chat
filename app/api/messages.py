from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.messages import service
from app.messages.service import MAX_MESSAGE_LENGTH
from app.models import User
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/conversations", tags=["messages"])


class MessageIn(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be blank")
        if len(stripped) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"content must be at most {MAX_MESSAGE_LENGTH} characters"
            )
        return stripped


class MessageOut(BaseModel):
    id: int
    sender_sub: str
    recipient_sub: str
    content: str | None = None
    deleted: bool = False
    edited_at: str | None = None
    created_at: str


class MessagePageOut(BaseModel):
    messages: list[MessageOut]
    next_before: int | None


class PeerOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class ConversationSummaryOut(BaseModel):
    peer: PeerOut
    last_message: MessageOut | None
    unread_count: int
    last_read_id: int


class ConversationsOut(BaseModel):
    conversations: list[ConversationSummaryOut]


class ReadIn(BaseModel):
    last_read_id: int = Field(ge=1)


class ReadOut(BaseModel):
    status: str
    last_read_id: int


@router.get("", response_model=ConversationsOut)
async def conversations_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationsOut:
    return ConversationsOut.model_validate(
        {"conversations": await service.conversation_summaries(db, user.sub)}
    )


@router.post("/{other_sub}/read", response_model=ReadOut)
async def mark_read(
    request: Request,
    other_sub: str,
    body: ReadIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ReadOut:
    await service.mark_read(db, user.sub, other_sub, body.last_read_id)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    await manager.send_to(
        other_sub,
        {
            "type": "read_receipt",
            "by_sub": user.sub,
            "peer_sub": other_sub,
            "last_read_id": body.last_read_id,
        },
    )
    return ReadOut(status="ok", last_read_id=body.last_read_id)


@router.post("/{other_sub}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    request: Request,
    other_sub: str,
    body: MessageIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await service.send_message(db, user.sub, other_sub, body.content)
    payload = service.message_payload(message)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message", "message": payload}
    await manager.send_to(message.sender_sub, event)
    await manager.send_to(message.recipient_sub, event)
    return MessageOut(**payload)


@router.get("/{other_sub}/messages", response_model=MessagePageOut)
async def message_history(
    other_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=service.HISTORY_MAX_LIMIT)] = (
        service.HISTORY_DEFAULT_LIMIT
    ),
) -> MessagePageOut:
    rows, next_before = await service.history(
        db, user.sub, other_sub, before=before, limit=limit
    )
    return MessagePageOut(
        messages=[MessageOut(**service.message_payload(item)) for item in rows],
        next_before=next_before,
    )


@router.patch("/{other_sub}/messages/{message_id}", response_model=MessageOut)
async def edit_message(
    request: Request,
    other_sub: str,
    message_id: int,
    body: MessageIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await service.edit_message(db, user.sub, other_sub, message_id, body.content)
    payload = service.message_payload(message)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message_edited", "message": payload}
    await manager.send_to(message.sender_sub, event)
    await manager.send_to(message.recipient_sub, event)
    return MessageOut(**payload)


@router.delete("/{other_sub}/messages/{message_id}", response_model=MessageOut)
async def delete_message(
    request: Request,
    other_sub: str,
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await service.delete_message(db, user.sub, other_sub, message_id)
    payload = service.message_payload(message)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message_deleted", "message": payload}
    await manager.send_to(message.sender_sub, event)
    await manager.send_to(message.recipient_sub, event)
    return MessageOut(**payload)
