import asyncio

from fakeredis.aioredis import FakeRedis

from app.sso.replay import MemoryReplayCache, RedisReplayCache


async def test_memory_cache_marks_replay() -> None:
    cache = MemoryReplayCache(ttl=60)
    assert await cache.check_and_add("j-1") is False
    assert await cache.check_and_add("j-1") is True


async def test_memory_cache_expires() -> None:
    cache = MemoryReplayCache(ttl=0)
    assert await cache.check_and_add("j-1") is False
    await asyncio.sleep(0.01)
    assert await cache.check_and_add("j-1") is False


async def test_redis_cache_atomic_replay_and_ttl() -> None:
    redis = FakeRedis(decode_responses=True)
    cache = RedisReplayCache(redis, ttl=60)
    assert await cache.check_and_add("j-1") is False
    assert await cache.check_and_add("j-1") is True
    assert await redis.ttl("lichat:replay:j-1") == 60


async def test_redis_cache_prefix_isolation() -> None:
    redis = FakeRedis(decode_responses=True)
    a = RedisReplayCache(redis, ttl=60, prefix="a:")
    b = RedisReplayCache(redis, ttl=60, prefix="b:")
    assert await a.check_and_add("j-1") is False
    assert await b.check_and_add("j-1") is False
