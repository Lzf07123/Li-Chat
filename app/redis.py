from __future__ import annotations

import json
from typing import cast

from redis.asyncio import Redis

from app.ws.manager import ConnectionManager

LOGOUT_CHANNEL = "lichat:logout"


def build_redis(url: str | None) -> Redis | None:
    if not url:
        return None
    return cast(Redis, Redis.from_url(url, decode_responses=True))


async def publish_logout(redis: Redis, sub: str) -> None:
    await redis.publish(LOGOUT_CHANNEL, json.dumps({"sub": sub}))


async def logout_subscriber(redis: Redis, manager: ConnectionManager) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(LOGOUT_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                payload = json.loads(message["data"])
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("sub"), str):
                await manager.disconnect_sub(payload["sub"], code=4401)
    finally:
        await pubsub.aclose()  # type: ignore[no-untyped-call]
