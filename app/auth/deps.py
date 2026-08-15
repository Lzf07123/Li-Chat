from __future__ import annotations

import secrets
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_session
from app.config import Settings
from app.db import get_db
from app.models import User


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    settings = cast(Settings, request.app.state.settings)
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="not authenticated")
    session = await get_session(
        db, session_id, sliding_ttl=settings.session_sliding_ttl
    )
    if session is None:
        raise HTTPException(status_code=401, detail="session invalid or expired")
    user = await db.get(User, session.user_sub)
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    request.state.session = session
    return user


async def require_csrf(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    settings = cast(Settings, request.app.state.settings)
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="not authenticated")
    session = await get_session(
        db, session_id, sliding_ttl=settings.session_sliding_ttl
    )
    if session is None:
        raise HTTPException(status_code=401, detail="session invalid or expired")
    token = request.headers.get("x-csrf-token")
    content_type = request.headers.get("content-type", "")
    if token is None and (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        form = await request.form()
        token = str(form.get("csrf_token") or "")
    if not token or not secrets.compare_digest(token, session.csrf_token):
        raise HTTPException(status_code=403, detail="csrf token missing or invalid")
