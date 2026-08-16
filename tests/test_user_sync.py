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


async def test_upsert_backfills_only_when_local_value_missing(
    db_session: AsyncSession,
) -> None:
    await upsert_user(db_session, USERINFO)
    user = (
        await db_session.execute(select(User).where(User.sub == "u-1001"))
    ).scalar_one()
    user.nickname = "本地昵称"
    user.picture = "/api/uploads/202608/local.png"
    await db_session.commit()
    user = await upsert_user(db_session, {**USERINFO, "nickname": "Alicia"})
    assert user.nickname == "本地昵称"
    assert (
        await db_session.execute(select(User).where(User.sub == "u-1001"))
    ).scalar_one().nickname == "本地昵称"
    assert (
        await db_session.execute(select(User).where(User.sub == "u-1001"))
    ).scalar_one().picture == "/api/uploads/202608/local.png"
