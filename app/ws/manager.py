from __future__ import annotations

from typing import Any, Protocol


class WSConnection(Protocol):
    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...

    async def send_json(self, data: Any, mode: str = "text") -> None: ...


class ConnectionManager:
    """单进程内存连接表，按用户 sub 维护活跃 WebSocket。"""

    def __init__(self) -> None:
        self._connections: dict[str, set[WSConnection]] = {}

    async def connect(self, sub: str, ws: WSConnection) -> None:
        self._connections.setdefault(sub, set()).add(ws)

    async def disconnect(self, sub: str, ws: WSConnection) -> None:
        connections = self._connections.get(sub)
        if connections is None:
            return
        connections.discard(ws)
        if not connections:
            self._connections.pop(sub, None)

    async def disconnect_sub(self, sub: str, code: int = 4401) -> None:
        connections = self._connections.pop(sub, set())
        for ws in list(connections):
            await ws.close(code=code)

    async def send_to(self, sub: str, payload: dict[str, Any]) -> None:
        for ws in list(self._connections.get(sub, set())):
            await ws.send_json(payload)
