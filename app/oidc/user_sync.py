from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def upsert_user(db: AsyncSession, userinfo: dict[str, Any]) -> User:
    sub = str(userinfo["sub"])
    user = (
        await db.execute(select(User).where(User.sub == sub))
    ).scalar_one_or_none()
    if user is None:
        user = User(sub=sub)
        db.add(user)
    if not user.nickname:
        user.nickname = userinfo.get("nickname")
    if not user.picture:
        user.picture = userinfo.get("picture")
    user.name = userinfo.get("name")
    user.email = userinfo.get("email")
    user.email_verified = userinfo.get("email_verified")
    await db.commit()
    return user
