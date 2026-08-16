from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.main import _ensure_message_columns


def test_ensure_message_columns_adds_group_columns(tmp_path) -> None:
    async def run() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}")
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                """
                CREATE TABLE messages (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sender_sub VARCHAR(64) NOT NULL,
                  recipient_sub VARCHAR(64) NOT NULL,
                  participant_lo VARCHAR(64) NOT NULL,
                  participant_hi VARCHAR(64) NOT NULL,
                  content TEXT NOT NULL,
                  created_at DATETIME NOT NULL,
                  CHECK (sender_sub != recipient_sub),
                  CHECK (participant_lo < participant_hi)
                )
                """
            )
            await conn.exec_driver_sql(
                "INSERT INTO messages (sender_sub, recipient_sub, participant_lo, "
                "participant_hi, content, created_at) "
                "VALUES ('u-a', 'u-b', 'u-a', 'u-b', '旧消息', '2026-01-01 00:00:00')"
            )
            await conn.run_sync(_ensure_message_columns)
            names = {
                row[1]
                for row in (
                    await conn.exec_driver_sql("PRAGMA table_info(messages)")
                ).fetchall()
            }
            result = await conn.exec_driver_sql(
                "SELECT content, conversation_type, group_id FROM messages"
            )
            row = result.fetchone()
        await engine.dispose()
        assert {"conversation_type", "group_id", "edited_at", "deleted_at"} <= names
        assert row == ("旧消息", "dm", None)

    asyncio.run(run())
