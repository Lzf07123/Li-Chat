from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.models import Session, User

router = APIRouter(prefix="/api", tags=["users"])


class MeOut(BaseModel):
    sub: str
    nickname: str | None
    name: str | None
    picture: str | None
    email: str | None
    csrf_token: str


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
