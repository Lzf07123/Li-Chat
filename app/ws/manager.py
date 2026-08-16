from __future__ import annotations

import time
from typing import Any, Protocol


class WSConnection(Protocol):
    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...

    async def send_json(self, data: Any, mode: str = "text") -> None: ...


class ConnectionManager:
    """单进程内存连接表，按用户 sub 维护活跃 WebSocket。"""

    def __init__(self) -> None:
        self._connections: dict[str, set[WSConnection]] = {}
        self._typing_slots: dict[tuple[str, str], float] = {}
        self._session_ids: dict[WSConnection, str] = {}

    def has(self, sub: str) -> bool:
        return bool(self._connections.get(sub))

    def count(self, sub: str) -> int:
        return len(self._connections.get(sub, set()))

    def typing_allowed(
        self, sender: str, target: str, min_interval: float = 2.0
    ) -> bool:
        key = (sender, target)
        now = time.monotonic()
        last = self._typing_slots.get(key)
        if last is not None and now - last < min_interval:
            return False
        self._typing_slots[key] = now
        if len(self._typing_slots) > 10_000:
            self._typing_slots = {
                slot: value
                for slot, value in self._typing_slots.items()
                if now - value < min_interval
            }
        return True

    async def connect(
        self, sub: str, ws: WSConnection, session_id: str | None = None
    ) -> None:
        self._connections.setdefault(sub, set()).add(ws)
        if session_id is not None:
            self._session_ids[ws] = session_id

    async def disconnect(self, sub: str, ws: WSConnection) -> None:
        connections = self._connections.get(sub)
        if connections is None:
            return
        connections.discard(ws)
        self._session_ids.pop(ws, None)
        if not connections:
            self._connections.pop(sub, None)

    async def disconnect_sub(self, sub: str, code: int = 4401) -> None:
        connections = self._connections.pop(sub, set())
        for ws in list(connections):
            self._session_ids.pop(ws, None)
            await ws.close(code=code)

    async def disconnect_session(
        self, sub: str, session_id: str, code: int = 4401
    ) -> None:
        connections = self._connections.get(sub)
        if connections is None:
            return
        targets = [
            ws
            for ws in list(connections)
            if self._session_ids.get(ws) == session_id
        ]
        for ws in targets:
            connections.discard(ws)
            self._session_ids.pop(ws, None)
            await ws.close(code=code)
        if not connections:
            self._connections.pop(sub, None)

    async def send_to(self, sub: str, payload: dict[str, Any]) -> None:
        for ws in list(self._connections.get(sub, set())):
            await ws.send_json(payload)
