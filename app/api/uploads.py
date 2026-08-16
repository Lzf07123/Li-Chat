from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_action_rate, require_csrf
from app.config import Settings
from app.db import get_db
from app.models import User
from app.uploads import service

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadOut(BaseModel):
    id: int
    url: str
    name: str
    size: int
    mime: str


@router.post("", response_model=UploadOut, status_code=201)
async def upload_file(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
    _rate: Annotated[None, Depends(require_action_rate)],
    file: Annotated[UploadFile, File()],
) -> UploadOut:
    settings = cast(Settings, request.app.state.settings)
    data = await file.read()
    result = await service.save_upload(
        db, settings, user.sub, file.filename or "upload", data
    )
    return UploadOut(**result)


@router.get("/{filename:path}")
async def download_upload(
    request: Request,
    filename: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    upload = await service.get_upload(db, filename)
    if upload.owner_sub != user.sub and not await service.referenced_for(
        db, f"/api/uploads/{filename}", user.sub
    ):
        raise HTTPException(status_code=403, detail="not your upload")
    settings = cast(Settings, request.app.state.settings)
    path = service.resolve_upload_root(settings) / upload.filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="upload not found")
    disposition = "inline" if upload.mime.startswith("image/") else "attachment"
    safe_name = (
        upload.original_name.replace('"', "")
        .replace("\r", "")
        .replace("\n", "")
        .strip()
        or "download"
    )
    return FileResponse(
        Path(path),
        media_type=upload.mime,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(safe_name)}",
            "X-Content-Type-Options": "nosniff",
        },
    )
