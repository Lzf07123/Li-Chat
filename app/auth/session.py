from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session
from app.timeutil import utcnow


async def create_session(
    db: AsyncSession,
    user_sub: str,
    *,
    sid: str | None = None,
    acr: str | None = None,
    sliding_ttl: int = 7200,
    absolute_ttl: int = 604800,
) -> Session:
    now = utcnow()
    session = Session(
        id=secrets.token_hex(32),
        user_sub=user_sub,
        sid=sid,
        acr=acr,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now + timedelta(seconds=sliding_ttl),
        absolute_expires_at=now + timedelta(seconds=absolute_ttl),
    )
    db.add(session)
    await db.commit()
    return session


async def get_session(
    db: AsyncSession, session_id: str, *, sliding_ttl: int = 7200
) -> Session | None:
    session = await db.get(Session, session_id)
    if session is None:
        return None
    now = utcnow()
    if now >= session.expires_at or now >= session.absolute_expires_at:
        return None
    session.last_seen_at = now
    session.expires_at = now + timedelta(seconds=sliding_ttl)
    await db.commit()
    return session


async def delete_session(db: AsyncSession, session_id: str) -> None:
    session = await db.get(Session, session_id)
    if session is not None:
        await db.delete(session)
        await db.commit()


async def delete_sessions_for(db: AsyncSession, user_sub: str, sid: str) -> int:
    result = await db.execute(
        delete(Session).where(Session.user_sub == user_sub, Session.sid == sid)
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def delete_all_sessions_for(db: AsyncSession, user_sub: str) -> int:
    result = await db.execute(delete(Session).where(Session.user_sub == user_sub))
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def set_session_cookie(
    response: Response,
    session_id: str,
    *,
    cookie_name: str,
    max_age: int,
    secure: bool,
) -> None:
    response.set_cookie(
        cookie_name,
        session_id,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, *, cookie_name: str) -> None:
    response.delete_cookie(cookie_name, path="/")
