from sqlalchemy.ext.asyncio import AsyncSession

from app.oidc.state import create_auth_state, pop_auth_state


async def test_state_is_single_use(db_session: AsyncSession) -> None:
    state = await create_auth_state(db_session, verifier="v-1", nonce="n-1", redirect_after="/")
    record = await pop_auth_state(db_session, state)
    assert record is not None
    assert record.verifier == "v-1"
    assert await pop_auth_state(db_session, state) is None


async def test_expired_state_returns_none(db_session: AsyncSession) -> None:
    state = await create_auth_state(
        db_session, verifier="v-1", nonce="n-1", redirect_after="/", ttl=-1
    )
    assert await pop_auth_state(db_session, state) is None
