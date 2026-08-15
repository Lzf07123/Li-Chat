from __future__ import annotations

import time
from typing import Protocol

from redis.asyncio import Redis


class ReplayCache(Protocol):
    """jti 防重放缓存接口：True 表示重放，原子完成判定与写入。"""

    async def check_and_add(self, jti: str) -> bool: ...


class MemoryReplayCache:
    """进程内 jti 防重放缓存；单进程部署够用，多副本需 Redis。"""

    def __init__(self, ttl: int = 300) -> None:
        self._seen: dict[str, float] = {}
        self._ttl = ttl

    async def check_and_add(self, jti: str) -> bool:
        self._prune()
        if jti in self._seen:
            return True
        self._seen[jti] = time.monotonic() + self._ttl
        return False

    def _prune(self) -> None:
        now = time.monotonic()
        for jti, deadline in list(self._seen.items()):
            if deadline <= now:
                del self._seen[jti]


class RedisReplayCache:
    """Redis 版 jti 防重放：SET NX EX 原子判定并写入，多副本共享。"""

    def __init__(
        self, redis: Redis, *, ttl: int = 300, prefix: str = "lichat:replay:"
    ) -> None:
        self._redis = redis
        self._ttl = ttl
        self._prefix = prefix

    async def check_and_add(self, jti: str) -> bool:
        result = await self._redis.set(self._prefix + jti, "1", ex=self._ttl, nx=True)
        return result is None
