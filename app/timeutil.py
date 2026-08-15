from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """返回 naive UTC 时间，避免 SQLite 对带时区时间的序列化差异。"""
    return datetime.now(UTC).replace(tzinfo=None)


def iso_utc(dt: datetime) -> str:
    """naive UTC → ISO8601 字符串（带 Z），供 API/WS 序列化。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat() + "Z"
