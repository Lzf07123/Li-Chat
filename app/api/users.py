from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.friends import service as friends_service
from app.models import Session, User

router = APIRouter(prefix="/api", tags=["users"])


class MeOut(BaseModel):
    sub: str
    nickname: str | None
    name: str | None
    picture: str | None
    email: str | None
    csrf_token: str


class SearchResultOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None
    friend_status: str


class SearchOut(BaseModel):
    results: list[SearchResultOut]


@router.get("/me", response_model=MeOut)
async def me(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> MeOut:
    session = cast(Session, request.state.session)
    return MeOut(
        sub=user.sub,
        nickname=user.nickname,
        name=user.name,
        picture=user.picture,
        email=user.email,
        csrf_token=session.csrf_token,
    )


@router.get("/users/search", response_model=SearchOut)
async def search_users(
    q: Annotated[str, Query(min_length=1, max_length=64)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchOut:
    results = await friends_service.search_users(db, user.sub, q)
    return SearchOut(results=results)
