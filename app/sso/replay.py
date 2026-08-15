from __future__ import annotations

import time


class ReplayCache:
    """进程内 jti 防重放缓存；单进程部署够用，多副本需换 Redis。"""

    def __init__(self, ttl: int = 300) -> None:
        self._seen: dict[str, float] = {}
        self._ttl = ttl

    def seen(self, jti: str) -> bool:
        self._prune()
        return jti in self._seen

    def add(self, jti: str) -> None:
        self._prune()
        self._seen[jti] = time.monotonic() + self._ttl

    def _prune(self) -> None:
        now = time.monotonic()
        for jti, deadline in list(self._seen.items()):
            if deadline <= now:
                del self._seen[jti]
