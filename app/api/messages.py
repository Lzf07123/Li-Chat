from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.polls import PollOut
from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.messages import service
from app.messages.service import MAX_MESSAGE_LENGTH
from app.models import Message, User
from app.polls.service import (
    POLL_OPTION_MAX,
    POLL_OPTIONS_MAX,
    POLL_OPTIONS_MIN,
    POLL_QUESTION_MAX,
)
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/conversations", tags=["messages"])


class MessageIn(BaseModel):
    content_type: Literal["text", "image", "file", "audio", "poll"] = "text"
    content: str = ""
    attachment: AttachmentIn | None = None
    reply_to_id: int | None = Field(default=None, ge=1)
    mentions: list[str] = []
    poll: PollIn | None = None

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str, info: ValidationInfo) -> str:
        stripped = value.strip()
        if info.data.get("content_type", "text") == "text" and not stripped:
            raise ValueError("content must not be blank")
        if len(stripped) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"content must be at most {MAX_MESSAGE_LENGTH} characters"
            )
        return stripped

    @field_validator("mentions")
    @classmethod
    def _validate_mentions(cls, value: list[str]) -> list[str]:
        if len(value) > service.MAX_MENTIONS:
            raise ValueError(f"at most {service.MAX_MENTIONS} mentions")
        return value


class AttachmentIn(BaseModel):
    url: str


class PollIn(BaseModel):
    question: str
    options: list[str]
    multiple: bool = False

    @field_validator("question")
    @classmethod
    def _validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or len(stripped) > POLL_QUESTION_MAX:
            raise ValueError(
                f"question must be 1-{POLL_QUESTION_MAX} characters"
            )
        return stripped

    @field_validator("options")
    @classmethod
    def _validate_options(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(option.strip() for option in value))
        if any(not option or len(option) > POLL_OPTION_MAX for option in cleaned):
            raise ValueError(
                f"each option must be 1-{POLL_OPTION_MAX} characters"
            )
        if len(cleaned) < POLL_OPTIONS_MIN or len(cleaned) > POLL_OPTIONS_MAX:
            raise ValueError(
                f"need {POLL_OPTIONS_MIN}-{POLL_OPTIONS_MAX} distinct options"
            )
        return cleaned


class AttachmentOut(BaseModel):
    name: str
    size: int | None = None
    mime: str | None = None
    url: str | None = None


class ReplyToOut(BaseModel):
    id: int
    sender_sub: str
    content: str | None = None
    deleted: bool = False
    content_type: str = "text"


class ForwardIn(BaseModel):
    message_id: int = Field(ge=1)


class ReactionCountOut(BaseModel):
    emoji: str
    count: int


class MessageOut(BaseModel):
    id: int
    sender_sub: str
    recipient_sub: str
    conversation_type: str = "dm"
    group_id: int | None = None
    content: str | None = None
    content_type: str = "text"
    forwarded: bool = False
    attachment: AttachmentOut | None = None
    reply_to: ReplyToOut | None = None
    mentions: list[str] = []
    starred: bool = False
    deleted: bool = False
    edited_at: str | None = None
    created_at: str
    reactions: list[ReactionCountOut] = []
    my_reactions: list[str] = []
    poll: PollOut | None = None
    read_count: int = 0


class ReactionIn(BaseModel):
    emoji: str

    @field_validator("emoji")
    @classmethod
    def _validate_emoji(cls, value: str) -> str:
        try:
            return service.clean_emoji(value)
        except ValueError as error:
            raise ValueError(str(error)) from error


class ReactionOut(BaseModel):
    message_id: int
    emoji: str
    action: str
    count: int


class MessagePageOut(BaseModel):
    messages: list[MessageOut]
    next_before: int | None


class PeerOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class ConversationSummaryOut(BaseModel):
    peer: PeerOut | None = None
    group: GroupSummaryOut | None = None
    last_message: MessageOut | None
    unread_count: int
    last_read_id: int
    pinned: bool = False
    muted: bool = False


class ConversationSettingsIn(BaseModel):
    kind: Literal["dm", "group"]
    key: str
    pinned: bool | None = None
    muted: bool | None = None


class ConversationSettingsOut(BaseModel):
    kind: str
    key: str
    pinned: bool
    muted: bool


class GroupSummaryOut(BaseModel):
    id: int
    name: str
    owner_sub: str
    member_count: int
    avatar_url: str | None = None


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


@router.patch("/settings", response_model=ConversationSettingsOut)
async def update_conversation_settings(
    body: ConversationSettingsIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ConversationSettingsOut:
    result = await service.set_conversation_setting(
        db, user.sub, body.kind, body.key, body.pinned, body.muted
    )
    return ConversationSettingsOut(**result)


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
    message = await service.send_message(
        db,
        user.sub,
        other_sub,
        body.content,
        content_type=body.content_type,
        attachment=body.attachment.model_dump() if body.attachment else None,
        reply_to_id=body.reply_to_id,
        mentions=body.mentions,
    )
    mention_subs = list(dict.fromkeys(body.mentions))
    reply = (
        await db.get(Message, message.reply_to_id)
        if message.reply_to_id is not None
        else None
    )
    payload = service.message_payload(message, reply, mention_subs)
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
    replies = await _replies_for(db, rows)
    mentions = await service.mentions_for(db, [item.id for item in rows])
    starred_ids = await service.starred_for(db, user.sub, [item.id for item in rows])
    reaction_map = await service.reactions_for(
        db, [item.id for item in rows], user.sub
    )
    messages: list[MessageOut] = []
    for item in rows:
        reply = (
            replies.get(item.reply_to_id)
            if item.reply_to_id is not None
            else None
        )
        data = service.message_payload(item, reply)
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
    return MessagePageOut(
        messages=messages,
        next_before=next_before,
    )


@router.post("/{other_sub}/forward", response_model=MessageOut, status_code=201)
async def forward_dm_message(
    request: Request,
    other_sub: str,
    body: ForwardIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await service.forward_message(
        db, user.sub, body.message_id, to_sub=other_sub
    )
    payload = service.message_payload(message)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message", "message": payload}
    await manager.send_to(message.sender_sub, event)
    await manager.send_to(message.recipient_sub, event)
    return MessageOut(**payload)


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
    reply = (
        await db.get(Message, message.reply_to_id)
        if message.reply_to_id is not None
        else None
    )
    payload = service.message_payload(message, reply)
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


@router.put("/{other_sub}/messages/{message_id}/reactions", response_model=ReactionOut)
async def add_reaction(
    request: Request,
    other_sub: str,
    message_id: int,
    body: ReactionIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ReactionOut:
    result = await service.set_reaction(
        db, user.sub, other_sub, message_id, body.emoji, add=True
    )
    await _broadcast_reaction(request, result, user.sub, other_sub)
    return ReactionOut(**result)


@router.delete("/{other_sub}/messages/{message_id}/reactions", response_model=ReactionOut)
async def remove_reaction(
    request: Request,
    other_sub: str,
    message_id: int,
    emoji: Annotated[str, Query(min_length=1, max_length=16)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ReactionOut:
    try:
        cleaned = service.clean_emoji(emoji)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    result = await service.set_reaction(
        db, user.sub, other_sub, message_id, cleaned, add=False
    )
    await _broadcast_reaction(request, result, user.sub, other_sub)
    return ReactionOut(**result)


async def _broadcast_reaction(
    request: Request, result: dict[str, Any], sender_sub: str, other_sub: str
) -> None:
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {
        "type": "message_reaction",
        "message_id": result["message_id"],
        "emoji": result["emoji"],
        "action": result["action"],
        "count": result["count"],
        "by_sub": sender_sub,
    }
    await manager.send_to(sender_sub, event)
    await manager.send_to(other_sub, event)


async def _replies_for(db: AsyncSession, rows: list[Message]) -> dict[int, Message]:
    reply_ids = [row.reply_to_id for row in rows if row.reply_to_id is not None]
    if not reply_ids:
        return {}
    targets = (
        await db.execute(select(Message).where(Message.id.in_(reply_ids)))
    ).scalars().all()
    return {target.id: target for target in targets}
