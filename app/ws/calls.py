from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends
from app.models import CallLog
from app.timeutil import utcnow
from app.ws.manager import ConnectionManager

CALL_OPS = frozenset({"offer", "answer", "ice", "reject", "end"})
CALL_PAYLOAD_MAX_BYTES = 16384


class CallManager:
    """进程内 1:1 呼叫状态机：idle → ringing → connected → ended。"""

    def __init__(self) -> None:
        self._calls: dict[tuple[str, str], str] = {}
        self._ice_slots: dict[tuple[str, str], float] = {}
        self._log_ids: dict[tuple[str, str], int] = {}

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

    def set_log_id(self, a: str, b: str, log_id: int) -> None:
        self._log_ids[self._key(a, b)] = log_id

    def log_id_for(self, a: str, b: str) -> int | None:
        return self._log_ids.get(self._key(a, b))

    def clear_log_id(self, a: str, b: str) -> None:
        self._log_ids.pop(self._key(a, b), None)

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
    kind = "audio"
    if message.get("kind") in {"audio", "video"}:
        kind = str(message["kind"])
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
            await _record_call(db, sender_sub, target, kind, "missed", ended=True)
            await manager.send_to(
                sender_sub,
                {"type": "call", "op": "unavailable", "from": target, "payload": {}},
            )
            return
        if not calls.offer(sender_sub, target):
            await _record_call(db, sender_sub, target, kind, "missed", ended=True)
            await manager.send_to(
                sender_sub,
                {"type": "call", "op": "busy", "from": target, "payload": {}},
            )
            return
        log_id = await _record_call(db, sender_sub, target, kind, None)
        calls.set_log_id(sender_sub, target, log_id)
    elif op == "answer":
        if not calls.answer(sender_sub, target):
            await manager.send_to(
                sender_sub,
                {"type": "call", "op": "invalid", "from": target, "payload": {}},
            )
            return
        answer_log_id = calls.log_id_for(sender_sub, target)
        if answer_log_id is not None:
            await _update_call(db, answer_log_id, "accepted")
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
        was_connected = calls.is_active(sender_sub, target) and calls._calls.get(
            calls._key(sender_sub, target)
        ) == "connected"
        end_log_id = calls.log_id_for(sender_sub, target)
        calls.clear_log_id(sender_sub, target)
        calls.end(sender_sub, target)
        if end_log_id is not None:
            status = "rejected" if op == "reject" else (
                "accepted" if was_connected else "missed"
            )
            await _update_call(db, end_log_id, status, ended=True)
    await manager.send_to(
        target,
        {"type": "call", "op": op, "from": sender_sub, "payload": payload},
    )


async def _record_call(
    db: AsyncSession,
    caller_sub: str,
    callee_sub: str,
    kind: str,
    status: str | None,
    *,
    ended: bool = False,
) -> int:
    log = CallLog(
        caller_sub=caller_sub,
        callee_sub=callee_sub,
        kind=kind,
        status=status,
        ended_at=utcnow() if ended else None,
    )
    db.add(log)
    await db.commit()
    return log.id


async def _update_call(
    db: AsyncSession, log_id: int, status: str, *, ended: bool = False
) -> None:
    log = await db.get(CallLog, log_id)
    if log is None:
        return
    log.status = status
    if ended:
        log.ended_at = utcnow()
    await db.commit()
