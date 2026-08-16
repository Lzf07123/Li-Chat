from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import User
from app.search import service

router = APIRouter(prefix="/api/search", tags=["search"])


class ConversationRefOut(BaseModel):
    type: Literal["dm", "group"]
    peer_sub: str | None = None
    peer_name: str | None = None
    group_id: int | None = None
    group_name: str | None = None


class SearchMessageOut(BaseModel):
    id: int
    sender_sub: str
    conversation: ConversationRefOut
    snippet: str
    created_at: str


class MessagesSearchOut(BaseModel):
    messages: list[SearchMessageOut]
    next_before: int | None


class ContactOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None
    friend_status: str


class ContactsSearchOut(BaseModel):
    contacts: list[ContactOut]


@router.get("", response_model=MessagesSearchOut | ContactsSearchOut)
async def search(
    kind: Literal["messages", "contacts"],
    q: Annotated[str, Query(min_length=1, max_length=64)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=service.SEARCH_MAX_LIMIT)] = (
        service.SEARCH_DEFAULT_LIMIT
    ),
) -> MessagesSearchOut | ContactsSearchOut:
    if kind == "messages":
        items, next_before = await service.search_messages(
            db, user.sub, q, before=before, limit=limit
        )
        return MessagesSearchOut(messages=items, next_before=next_before)
    return ContactsSearchOut(
        contacts=await service.search_contacts(db, user.sub, q, limit=limit)
    )
