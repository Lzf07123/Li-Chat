from __future__ import annotations

from typing import cast

from redis.asyncio import Redis

LOGOUT_CHANNEL = "lichat:logout"


def build_redis(url: str | None) -> Redis | None:
    if not url:
        return None
    return cast(Redis, Redis.from_url(url, decode_responses=True))
