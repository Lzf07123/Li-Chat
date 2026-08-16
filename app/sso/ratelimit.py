from __future__ import annotations

import time
from collections import deque


class SlidingWindowRateLimiter:
    """进程内滑动窗口限流，按 key 记录最近窗口内的时间戳。"""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._buckets: dict[str, deque[float]] = {}

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        bucket = self._buckets.setdefault(key, deque())
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            retry_after = max(1, int(self.window - (now - bucket[0])) + 1)
            return False, retry_after
        bucket.append(now)
        if len(self._buckets) > 10_000:
            self._buckets = {k: v for k, v in self._buckets.items() if v}
        return True, 0
