from __future__ import annotations

import re
import secrets
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import GroupMember, Message, Upload
from app.timeutil import utcnow

EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "audio/webm": ".webm",
    "audio/mp4": ".m4a",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}

_FILENAME_RE = re.compile(r"^\d{6}/[A-Za-z0-9_-]{16,64}\.[a-z0-9]{2,5}$")


def detect_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "audio/mp4"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.lstrip().startswith(b"<"):
        return None
    if b"\x00" not in data:
        return "text/plain"
    return None


def resolve_upload_root(settings: Settings) -> Path:
    root = Path(settings.upload_dir).expanduser()
    return root if root.is_absolute() else Path.cwd() / root


def valid_filename(filename: str) -> bool:
    return _FILENAME_RE.fullmatch(filename) is not None


async def save_upload(
    db: AsyncSession,
    settings: Settings,
    owner_sub: str,
    original_name: str,
    data: bytes,
) -> dict[str, Any]:
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"file exceeds {settings.upload_max_mb}MB limit",
        )
    if not data:
        raise HTTPException(status_code=422, detail="file must not be empty")
    mime = detect_mime(data)
    if mime is None:
        raise HTTPException(status_code=415, detail="unsupported file type")
    extension = EXT_BY_MIME[mime]
    relative = f"{utcnow().strftime('%Y%m')}/{secrets.token_urlsafe(16)}{extension}"
    target = resolve_upload_root(settings) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    upload = Upload(
        owner_sub=owner_sub,
        filename=relative,
        original_name=original_name[:255],
        mime=mime,
        size=len(data),
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return {
        "id": upload.id,
        "url": f"/api/uploads/{relative}",
        "name": upload.original_name,
        "size": upload.size,
        "mime": upload.mime,
    }


async def get_upload(db: AsyncSession, filename: str) -> Upload:
    if not valid_filename(filename):
        raise HTTPException(status_code=404, detail="upload not found")
    upload = (
        await db.execute(select(Upload).where(Upload.filename == filename))
    ).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="upload not found")
    return upload


async def referenced_for(db: AsyncSession, url: str, viewer_sub: str) -> bool:
    """附件是否被「查看者可参与的会话」引用（用于回源授权）。"""
    group_ids = select(GroupMember.group_id).where(GroupMember.user_sub == viewer_sub)
    result = await db.execute(
        select(Message.id)
        .where(
            Message.attachment_url == url,
            or_(
                and_(
                    Message.conversation_type == "dm",
                    or_(
                        Message.participant_lo == viewer_sub,
                        Message.participant_hi == viewer_sub,
                    ),
                ),
                and_(
                    Message.conversation_type == "group",
                    Message.group_id.in_(group_ids),
                ),
            ),
        )
        .limit(1)
    )
    return result.first() is not None
