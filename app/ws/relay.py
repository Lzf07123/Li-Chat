from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends
from app.ws.manager import ConnectionManager

TYPING_ACTIONS = frozenset({"start", "stop"})


async def relay_typing(
    db: AsyncSession,
    manager: ConnectionManager,
    sender_sub: str,
    payload: dict[str, Any],
) -> bool:
    """校验并中继 typing 信令；拒绝时返回 False（调用方静默丢弃并计数）。"""
    target = payload.get("to")
    action = payload.get("action")
    if not isinstance(target, str) or action not in TYPING_ACTIONS:
        return False
    if sender_sub == target:
        return False
    if not await are_friends(db, sender_sub, target):
        return False
    if not manager.typing_allowed(sender_sub, target):
        return False
    await manager.send_to(
        target, {"type": "typing", "from": sender_sub, "action": action}
    )
    return True
