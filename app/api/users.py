from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.search import ConversationRefOut
from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.friends import service as friends_service
from app.groups import service as groups_service
from app.messages import service as messages_service
from app.models import CallLog, Session, User
from app.timeutil import iso_utc, utcnow
from app.uploads.service import get_upload
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api", tags=["users"])


async def _collect_history(
    db: AsyncSession,
    me_sub: str,
    *,
    friend_sub: str | None = None,
    group_id: int | None = None,
    max_pages: int = 20,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    before: int | None = None
    for _ in range(max_pages):
        if friend_sub is not None:
            rows, next_before = await messages_service.history(
                db, me_sub, friend_sub, before=before, limit=100
            )
        else:
            assert group_id is not None
            rows, next_before = await messages_service.group_history(
                db, me_sub, group_id, before=before, limit=100
            )
        items.extend(messages_service.message_payload(row) for row in rows)
        if next_before is None:
            break
        before = next_before
    return items


class MeOut(BaseModel):
    sub: str
    nickname: str | None
    name: str | None
    picture: str | None
    email: str | None
    bio: str | None = None
    csrf_token: str


class ProfileIn(BaseModel):
    nickname: str | None = None
    bio: str | None = None

    @field_validator("nickname")
    @classmethod
    def _validate_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped or len(stripped) > 32:
            raise ValueError("nickname must be 1-32 characters")
        return stripped

    @field_validator("bio")
    @classmethod
    def _validate_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if len(stripped) > 200:
            raise ValueError("bio must be at most 200 characters")
        return stripped


class AvatarIn(BaseModel):
    url: str


class SearchResultOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None
    friend_status: str


class SearchOut(BaseModel):
    results: list[SearchResultOut]


class StarOut(BaseModel):
    message_id: int
    starred: bool


class StarredItemOut(BaseModel):
    id: int
    sender_sub: str
    conversation: ConversationRefOut
    content: str | None = None
    content_type: str = "text"
    deleted: bool = False
    created_at: str


class StarsOut(BaseModel):
    messages: list[StarredItemOut]
    next_before: int | None


class SessionOut(BaseModel):
    id: str
    created_at: str
    last_seen_at: str
    expires_at: str
    current: bool


class SessionsOut(BaseModel):
    sessions: list[SessionOut]


class StatusOut(BaseModel):
    status: str


class CallPeerOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class CallLogOut(BaseModel):
    id: int
    kind: str
    status: str | None = None
    started_at: str
    ended_at: str | None = None
    peer: CallPeerOut


class CallsOut(BaseModel):
    calls: list[CallLogOut]
    next_before: int | None


def _me_payload(user: User, session: Session) -> MeOut:
    return MeOut(
        sub=user.sub,
        nickname=user.nickname,
        name=user.name,
        picture=user.picture,
        email=user.email,
        bio=user.bio,
        csrf_token=session.csrf_token,
    )


@router.get("/me", response_model=MeOut)
async def me(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> MeOut:
    session = cast(Session, request.state.session)
    return _me_payload(user, session)


@router.patch("/me", response_model=MeOut)
async def update_profile(
    request: Request,
    body: ProfileIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MeOut:
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.bio is not None:
        user.bio = body.bio
    await db.commit()
    return _me_payload(user, cast(Session, request.state.session))


@router.post("/me/avatar", response_model=MeOut)
async def update_avatar(
    request: Request,
    body: AvatarIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MeOut:
    prefix = "/api/uploads/"
    if not body.url.startswith(prefix):
        raise HTTPException(status_code=422, detail="invalid avatar url")
    upload = await get_upload(db, body.url[len(prefix) :])
    if upload.owner_sub != user.sub:
        raise HTTPException(status_code=403, detail="avatar must be your upload")
    if not upload.mime.startswith("image/"):
        raise HTTPException(status_code=422, detail="avatar must be an image")
    user.picture = body.url
    await db.commit()
    return _me_payload(user, cast(Session, request.state.session))


@router.put("/messages/{message_id}/star", response_model=StarOut)
async def star_message(
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StarOut:
    result = await messages_service.set_star(
        db, user.sub, message_id, starred=True
    )
    return StarOut(**result)


@router.delete("/messages/{message_id}/star", response_model=StarOut)
async def unstar_message(
    message_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StarOut:
    result = await messages_service.set_star(
        db, user.sub, message_id, starred=False
    )
    return StarOut(**result)


@router.get("/me/stars", response_model=StarsOut)
async def starred_messages(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> StarsOut:
    items, next_before = await messages_service.starred_messages(
        db, user.sub, cursor=cursor, limit=limit
    )
    return StarsOut(messages=items, next_before=next_before)


@router.get("/me/sessions", response_model=SessionsOut)
async def sessions_list(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionsOut:
    current = cast(Session, request.state.session)
    rows = (
        await db.execute(
            select(Session)
            .where(Session.user_sub == user.sub)
            .order_by(Session.created_at.desc())
        )
    ).scalars().all()
    return SessionsOut(
        sessions=[
            SessionOut(
                id=row.id,
                created_at=iso_utc(row.created_at),
                last_seen_at=iso_utc(row.last_seen_at),
                expires_at=iso_utc(row.expires_at),
                current=row.id == current.id,
            )
            for row in rows
        ]
    )


@router.delete("/me/sessions/{session_id}", response_model=StatusOut)
async def revoke_session(
    request: Request,
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    target = await db.get(Session, session_id)
    if target is None or target.user_sub != user.sub:
        raise HTTPException(status_code=404, detail="session not found")
    await db.delete(target)
    await db.commit()
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    await manager.disconnect_session(user.sub, session_id)
    return StatusOut(status="revoked")


@router.delete("/me/sessions", response_model=StatusOut)
async def revoke_other_sessions(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    current = cast(Session, request.state.session)
    rows = (
        await db.execute(
            select(Session).where(
                Session.user_sub == user.sub, Session.id != current.id
            )
        )
    ).scalars().all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    for row in rows:
        await manager.disconnect_session(user.sub, row.id)
    return StatusOut(status="ok")


@router.get("/me/calls", response_model=CallsOut)
async def calls_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> CallsOut:
    stmt = (
        select(CallLog)
        .where(
            or_(CallLog.caller_sub == user.sub, CallLog.callee_sub == user.sub)
        )
        .order_by(CallLog.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(CallLog.id < cursor)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    page = list(rows[:limit])
    peer_subs = {
        row.callee_sub if row.caller_sub == user.sub else row.caller_sub
        for row in page
    }
    users: dict[str, User] = {}
    if peer_subs:
        found = (
            await db.execute(select(User).where(User.sub.in_(list(peer_subs))))
        ).scalars().all()
        users = {found_user.sub: found_user for found_user in found}
    items: list[CallLogOut] = []
    for row in page:
        peer_sub = row.callee_sub if row.caller_sub == user.sub else row.caller_sub
        peer = users.get(peer_sub)
        items.append(
            CallLogOut(
                id=row.id,
                kind=row.kind,
                status=row.status,
                started_at=iso_utc(row.started_at),
                ended_at=iso_utc(row.ended_at) if row.ended_at else None,
                peer=CallPeerOut(
                    sub=peer_sub,
                    nickname=peer.nickname if peer else None,
                    name=peer.name if peer else None,
                    picture=peer.picture if peer else None,
                ),
            )
        )
    next_before = page[-1].id if has_more and page else None
    return CallsOut(calls=items, next_before=next_before)


@router.get("/me/export")
async def export_my_data(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    friends = await friends_service.list_friends(db, user.sub)
    groups = await groups_service.list_groups(db, user.sub)
    dm_messages: dict[str, list[dict[str, object]]] = {}
    for friend in friends:
        sub = friend.get("sub")
        if isinstance(sub, str):
            dm_messages[sub] = await _collect_history(db, user.sub, friend_sub=sub)
    group_messages: dict[str, list[dict[str, object]]] = {}
    for group in groups:
        group_messages[str(group["id"])] = await _collect_history(
            db, user.sub, group_id=group["id"]
        )
    stars, _ = await messages_service.starred_messages(db, user.sub, limit=50)
    data = {
        "exported_at": iso_utc(utcnow()),
        "profile": {
            "sub": user.sub,
            "nickname": user.nickname,
            "name": user.name,
            "picture": user.picture,
            "email": user.email,
            "bio": user.bio,
        },
        "friends": friends,
        "groups": groups,
        "dm_messages": dm_messages,
        "group_messages": group_messages,
        "stars": stars,
    }
    filename = f"lichat-export-{utcnow().strftime('%Y%m%d')}.json"
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/users/search", response_model=SearchOut)
async def search_users(
    q: Annotated[str, Query(min_length=1, max_length=64)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchOut:
    results = await friends_service.search_users(db, user.sub, q)
    return SearchOut(results=results)
