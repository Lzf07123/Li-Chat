from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """返回 naive UTC 时间，避免 SQLite 对带时区时间的序列化差异。"""
    return datetime.now(UTC).replace(tzinfo=None)
