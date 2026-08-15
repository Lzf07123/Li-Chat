from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.oidc.user_sync import upsert_user

USERINFO = {
    "sub": "u-1001",
    "nickname": "Alice",
    "name": "Alice Zhang",
    "picture": "https://mock-idp.test/a.jpg",
}


async def test_upsert_creates_user(db_session: AsyncSession) -> None:
    user = await upsert_user(db_session, USERINFO)
    assert user.sub == "u-1001"
    assert user.nickname == "Alice"
    count = len(
        (await db_session.execute(select(User).where(User.sub == "u-1001"))).all()
    )
    assert count == 1


async def test_upsert_updates_existing_user(db_session: AsyncSession) -> None:
    await upsert_user(db_session, USERINFO)
    user = await upsert_user(db_session, {**USERINFO, "nickname": "Alicia"})
    assert user.nickname == "Alicia"
    assert (
        await db_session.execute(select(User).where(User.sub == "u-1001"))
    ).scalar_one().nickname == "Alicia"
