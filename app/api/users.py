from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.search import ConversationRefOut
from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.friends import service as friends_service
from app.messages import service as messages_service
from app.models import Session, User
from app.uploads.service import get_upload

router = APIRouter(prefix="/api", tags=["users"])


class MeOut(BaseModel):
    sub: str
    nickname: str | None
    name: str | None
    picture: str | None
    email: str | None
    bio: str | None = None
    csrf_token: str


class ProfileIn(BaseModel):
    nickname: str | None = None
    bio: str | None = None

    @field_validator("nickname")
    @classmethod
    def _validate_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped or len(stripped) > 32:
            raise ValueError("nickname must be 1-32 characters")
        return stripped

    @field_validator("bio")
    @classmethod
    def _validate_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if len(stripped) > 200:
            raise ValueError("bio must be at most 200 characters")
        return stripped


class AvatarIn(BaseModel):
    url: str


class SearchResultOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None
    friend_status: str


class SearchOut(BaseModel):
    results: list[SearchResultOut]


class StarOut(BaseModel):
    message_id: int
    starred: bool


class StarredItemOut(BaseModel):
    id: int
    sender_sub: str
    conversation: ConversationRefOut
    content: str | None = None
    content_type: str = "text"
    deleted: bool = False
    created_at: str


class StarsOut(BaseModel):
    messages: list[StarredItemOut]
    next_before: int | None


def _me_payload(user: User, session: Session) -> MeOut:
    return MeOut(
        sub=user.sub,
        nickname=user.nickname,
        name=user.name,
        picture=user.picture,
        email=user.email,
        bio=user.bio,
        csrf_token=session.csrf_token,
    )


@router.get("/me", response_model=MeOut)
async def me(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> MeOut:
    session = cast(Session, request.state.session)
    return _me_payload(user, session)


@router.patch("/me", response_model=MeOut)
async def update_profile(
    request: Request,
    body: ProfileIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MeOut:
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.bio is not None:
        user.bio = body.bio
    await db.commit()
    return _me_payload(user, cast(Session, request.state.session))


@router.post("/me/avatar", response_model=MeOut)
async def update_avatar(
    request: Request,
    body: AvatarIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MeOut:
    prefix = "/api/uploads/"
    if not body.url.startswith(prefix):
        raise HTTPException(status_code=422, detail="invalid avatar url")
    upload = await get_upload(db, body.url[len(prefix) :])
    if upload.owner_sub != user.sub:
        raise HTTPException(status_code=403, detail="avatar must be your upload")
    if not upload.mime.startswith("image/"):
        raise HTTPException(status_code=422, detail="avatar must be an image")
    user.picture = body.url
    await db.commit()
    return _me_payload(user, cast(Session, request.state.session))


@router.put("/messages/{message_id}/star", response_model=StarOut)
async def star_message(
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StarOut:
    result = await messages_service.set_star(
        db, user.sub, message_id, starred=True
    )
    return StarOut(**result)


@router.delete("/messages/{message_id}/star", response_model=StarOut)
async def unstar_message(
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StarOut:
    result = await messages_service.set_star(
        db, user.sub, message_id, starred=False
    )
    return StarOut(**result)


@router.get("/me/stars", response_model=StarsOut)
async def starred_messages(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> StarsOut:
    items, next_before = await messages_service.starred_messages(
        db, user.sub, cursor=cursor, limit=limit
    )
    return StarsOut(messages=items, next_before=next_before)


@router.get("/users/search", response_model=SearchOut)
async def search_users(
    q: Annotated[str, Query(min_length=1, max_length=64)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchOut:
    results = await friends_service.search_users(db, user.sub, q)
    return SearchOut(results=results)
