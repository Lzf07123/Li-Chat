from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends
from app.ws.manager import ConnectionManager

CALL_OPS = frozenset({"offer", "answer", "ice", "reject", "end"})
CALL_PAYLOAD_MAX_BYTES = 16384


class CallManager:
    """进程内 1:1 呼叫状态机：idle → ringing → connected → ended。"""

    def __init__(self) -> None:
        self._calls: dict[tuple[str, str], str] = {}
        self._ice_slots: dict[tuple[str, str], float] = {}

    @staticmethod
    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a < b else (b, a)

    def is_active(self, a: str, b: str) -> bool:
        return self._calls.get(self._key(a, b)) in {"ringing", "connected"}

    def offer(self, a: str, b: str) -> bool:
        key = self._key(a, b)
        if key in self._calls:
            return False
        self._calls[key] = "ringing"
        return True

    def answer(self, a: str, b: str) -> bool:
        key = self._key(a, b)
        if self._calls.get(key) == "ringing":
            self._calls[key] = "connected"
            return True
        return False

    def end(self, a: str, b: str) -> None:
        self._calls.pop(self._key(a, b), None)

    def ice_allowed(self, a: str, b: str, min_interval: float = 0.05) -> bool:
        key = self._key(a, b)
        now = time.monotonic()
        last = self._ice_slots.get(key)
        if last is not None and now - last < min_interval:
            return False
        self._ice_slots[key] = now
        if len(self._ice_slots) > 10_000:
            self._ice_slots = {
                slot: value
                for slot, value in self._ice_slots.items()
                if now - value < min_interval
            }
        return True


async def handle_call(
    db: AsyncSession,
    manager: ConnectionManager,
    calls: CallManager,
    sender_sub: str,
    message: dict[str, Any],
) -> None:
    """校验并中继呼叫信令；非法/越权请求静默丢弃或只回错误给发起方。"""
    op = message.get("op")
    target = message.get("to")
    payload = message.get("payload")
    if op not in CALL_OPS or not isinstance(target, str) or sender_sub == target:
        return
    if not isinstance(payload, dict):
        payload = {}
    try:
        size = len(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        )
    except (TypeError, ValueError):
        size = CALL_PAYLOAD_MAX_BYTES + 1
    if size > CALL_PAYLOAD_MAX_BYTES:
        await manager.send_to(
            sender_sub,
            {"type": "call", "op": "error", "from": target, "payload": {}},
        )
        return
    if not await are_friends(db, sender_sub, target):
        return
    if op == "offer":
        if not manager.has(target):
            await manager.send_to(
                sender_sub,
                {"type": "call", "op": "unavailable", "from": target, "payload": {}},
            )
            return
        if not calls.offer(sender_sub, target):
            await manager.send_to(
                sender_sub,
                {"type": "call", "op": "busy", "from": target, "payload": {}},
            )
            return
    elif op == "answer":
        if not calls.answer(sender_sub, target):
            await manager.send_to(
                sender_sub,
                {"type": "call", "op": "invalid", "from": target, "payload": {}},
            )
            return
    elif op == "ice":
        if not calls.is_active(sender_sub, target) or not calls.ice_allowed(
            sender_sub, target
        ):
            await manager.send_to(
                sender_sub,
                {"type": "call", "op": "invalid", "from": target, "payload": {}},
            )
            return
    else:
        calls.end(sender_sub, target)
    await manager.send_to(
        target,
        {"type": "call", "op": op, "from": sender_sub, "payload": payload},
    )
