from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthState
from app.timeutil import utcnow


async def create_auth_state(
    db: AsyncSession,
    *,
    verifier: str,
    nonce: str,
    redirect_after: str,
    ttl: int = 600,
) -> str:
    state = secrets.token_urlsafe(32)
    db.add(
        AuthState(
            state=state,
            verifier=verifier,
            nonce=nonce,
            redirect_after=redirect_after,
            expires_at=utcnow() + timedelta(seconds=ttl),
        )
    )
    await db.commit()
    return state


async def pop_auth_state(db: AsyncSession, state: str) -> AuthState | None:
    """取出并删除授权状态；只能使用一次，过期返回 None。"""
    record = (
        await db.execute(select(AuthState).where(AuthState.state == state))
    ).scalar_one_or_none()
    if record is None:
        return None
    await db.delete(record)
    await db.commit()
    if record.expires_at < utcnow():
        return None
    return record
