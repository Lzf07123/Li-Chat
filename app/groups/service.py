from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends
from app.models import (
    Group,
    GroupMember,
    GroupRead,
    Message,
    MessageMention,
    Reaction,
    User,
    UserConversationSetting,
    UserStar,
)
from app.timeutil import iso_utc
from app.uploads.service import get_upload

GROUP_NAME_MAX = 64
GROUP_MEMBERS_MAX = 200
INVITE_BATCH_MAX = 20
GROUP_ANNOUNCEMENT_MAX = 2000


def clean_name(value: str) -> str:
    stripped = value.strip()
    if not stripped or len(stripped) > GROUP_NAME_MAX:
        raise ValueError(f"group name must be 1-{GROUP_NAME_MAX} characters")
    return stripped


def profile(user: User) -> dict[str, str | None]:
    return {
        "sub": user.sub,
        "nickname": user.nickname,
        "name": user.name,
        "picture": user.picture,
    }


async def member_subs(db: AsyncSession, group_id: int) -> list[str]:
    rows = (
        await db.execute(
            select(GroupMember.user_sub).where(GroupMember.group_id == group_id)
        )
    ).scalars().all()
    return list(rows)


async def membership(
    db: AsyncSession, group_id: int, user_sub: str
) -> GroupMember | None:
    return await db.get(GroupMember, (group_id, user_sub))


async def _require_role(
    db: AsyncSession, group_id: int, user_sub: str, roles: set[str]
) -> GroupMember:
    member_row = await membership(db, group_id, user_sub)
    if member_row is None:
        raise HTTPException(status_code=404, detail="group not found")
    if member_row.role not in roles:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return member_row


async def group_payload(db: AsyncSession, group: Group) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(GroupMember)
            .where(GroupMember.group_id == group.id)
            .order_by(GroupMember.joined_at, GroupMember.user_sub)
        )
    ).scalars().all()
    subs = [row.user_sub for row in rows]
    users: dict[str, User] = {}
    if subs:
        found = (await db.execute(select(User).where(User.sub.in_(subs)))).scalars().all()
        users = {user.sub: user for user in found}
    members: list[dict[str, Any]] = []
    for row in rows:
        user = users.get(row.user_sub)
        if user is None:
            continue
        members.append(
            {
                "user": profile(user),
                "role": row.role,
                "muted": row.muted,
                "joined_at": iso_utc(row.joined_at),
            }
        )
    return {
        "id": group.id,
        "name": group.name,
        "owner_sub": group.owner_sub,
        "announcement": group.announcement,
        "avatar_url": group.avatar_url,
        "created_at": iso_utc(group.created_at),
        "members": members,
    }


async def create_group(
    db: AsyncSession, creator_sub: str, name: str, member_subs: list[str]
) -> dict[str, Any]:
    cleaned = clean_name(name)
    subs = list(dict.fromkeys(member_subs))
    if creator_sub in subs:
        raise HTTPException(status_code=400, detail="creator is already a member")
    if len(subs) > INVITE_BATCH_MAX:
        raise HTTPException(
            status_code=422, detail=f"at most {INVITE_BATCH_MAX} invitees per request"
        )
    for sub in subs:
        if await db.get(User, sub) is None:
            raise HTTPException(status_code=404, detail="invitee not found")
        if not await are_friends(db, creator_sub, sub):
            raise HTTPException(status_code=403, detail="invitees must be your friends")
    if 1 + len(subs) > GROUP_MEMBERS_MAX:
        raise HTTPException(status_code=409, detail="group capacity exceeded")
    group = Group(name=cleaned, owner_sub=creator_sub)
    db.add(group)
    await db.flush()
    db.add(GroupMember(group_id=group.id, user_sub=creator_sub, role="owner"))
    for sub in subs:
        db.add(GroupMember(group_id=group.id, user_sub=sub, role="member"))
    await db.commit()
    return await group_payload(db, group)


async def list_groups(db: AsyncSession, me_sub: str) -> list[dict[str, Any]]:
    group_ids = select(GroupMember.group_id).where(GroupMember.user_sub == me_sub)
    rows = (
        await db.execute(
            select(Group).where(Group.id.in_(group_ids)).order_by(Group.id.desc())
        )
    ).scalars().all()
    return [await group_payload(db, group) for group in rows]


async def get_group(db: AsyncSession, me_sub: str, group_id: int) -> dict[str, Any]:
    await _require_role(db, group_id, me_sub, {"owner", "admin", "member"})
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    return await group_payload(db, group)


async def rename_group(
    db: AsyncSession, me_sub: str, group_id: int, name: str
) -> dict[str, Any]:
    await _require_role(db, group_id, me_sub, {"owner", "admin"})
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    group.name = clean_name(name)
    await db.commit()
    return await group_payload(db, group)


async def add_members(
    db: AsyncSession, actor_sub: str, group_id: int, invitee_subs: list[str]
) -> dict[str, Any]:
    await _require_role(db, group_id, actor_sub, {"owner", "admin"})
    subs = list(dict.fromkeys(invitee_subs))
    if len(subs) > INVITE_BATCH_MAX:
        raise HTTPException(
            status_code=422, detail=f"at most {INVITE_BATCH_MAX} invitees per request"
        )
    existing = set(await member_subs(db, group_id))
    for sub in subs:
        if await db.get(User, sub) is None:
            raise HTTPException(status_code=404, detail="invitee not found")
        if not await are_friends(db, actor_sub, sub):
            raise HTTPException(status_code=403, detail="invitees must be your friends")
    if len(existing | set(subs)) > GROUP_MEMBERS_MAX:
        raise HTTPException(status_code=409, detail="group capacity exceeded")
    for sub in subs:
        if sub not in existing:
            db.add(GroupMember(group_id=group_id, user_sub=sub, role="member"))
    await db.commit()
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    return await group_payload(db, group)


async def remove_member(
    db: AsyncSession, actor_sub: str, group_id: int, target_sub: str
) -> None:
    actor = await _require_role(db, group_id, actor_sub, {"owner", "admin"})
    target = await membership(db, group_id, target_sub)
    if target is None:
        raise HTTPException(status_code=404, detail="member not found")
    if target.role == "owner":
        raise HTTPException(status_code=403, detail="cannot remove the owner")
    if actor.role == "admin" and target.role == "admin":
        raise HTTPException(status_code=403, detail="admins cannot remove each other")
    if target_sub == actor_sub:
        raise HTTPException(status_code=400, detail="use leave instead")
    await db.delete(target)
    await db.commit()


async def set_member_role(
    db: AsyncSession, actor_sub: str, group_id: int, target_sub: str, role: str
) -> None:
    actor = await _require_role(db, group_id, actor_sub, {"owner"})
    if target_sub == actor_sub:
        raise HTTPException(status_code=400, detail="cannot change your own role")
    if actor.role != "owner":
        raise HTTPException(status_code=403, detail="only the owner can change roles")
    target = await membership(db, group_id, target_sub)
    if target is None:
        raise HTTPException(status_code=404, detail="member not found")
    if target.role == "owner":
        raise HTTPException(status_code=403, detail="cannot change the owner's role")
    target.role = role
    await db.commit()


async def set_member_mute(
    db: AsyncSession, actor_sub: str, group_id: int, target_sub: str, muted: bool
) -> None:
    await _require_role(db, group_id, actor_sub, {"owner", "admin"})
    target = await membership(db, group_id, target_sub)
    if target is None:
        raise HTTPException(status_code=404, detail="member not found")
    if target_sub == actor_sub:
        raise HTTPException(status_code=400, detail="cannot mute yourself")
    if target.role in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="cannot mute owners or admins")
    target.muted = muted
    await db.commit()


async def leave_group(db: AsyncSession, me_sub: str, group_id: int) -> None:
    member_row = await membership(db, group_id, me_sub)
    if member_row is None:
        raise HTTPException(status_code=404, detail="group not found")
    if member_row.role == "owner":
        raise HTTPException(status_code=409, detail="owner must transfer before leaving")
    await db.delete(member_row)
    await db.commit()


async def transfer_ownership(
    db: AsyncSession, me_sub: str, group_id: int, new_owner_sub: str
) -> None:
    await _require_role(db, group_id, me_sub, {"owner"})
    target = await membership(db, group_id, new_owner_sub)
    if target is None:
        raise HTTPException(status_code=404, detail="member not found")
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    actor = await membership(db, group_id, me_sub)
    if actor is not None:
        actor.role = "member"
    target.role = "owner"
    group.owner_sub = new_owner_sub
    await db.commit()


async def set_announcement(
    db: AsyncSession, me_sub: str, group_id: int, text: str
) -> dict[str, Any]:
    await _require_role(db, group_id, me_sub, {"owner", "admin"})
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    group.announcement = text
    await db.commit()
    return await group_payload(db, group)


async def dissolve_group(
    db: AsyncSession, me_sub: str, group_id: int
) -> tuple[dict[str, Any], list[str]]:
    await _require_role(db, group_id, me_sub, {"owner"})
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    subs = await member_subs(db, group_id)
    payload = {
        "id": group.id,
        "name": group.name,
        "owner_sub": group.owner_sub,
        "member_count": len(subs),
    }
    message_ids = select(Message.id).where(Message.group_id == group_id)
    await db.execute(delete(MessageMention).where(MessageMention.message_id.in_(message_ids)))
    await db.execute(delete(Reaction).where(Reaction.message_id.in_(message_ids)))
    await db.execute(delete(UserStar).where(UserStar.message_id.in_(message_ids)))
    await db.execute(delete(Message).where(Message.group_id == group_id))
    await db.execute(delete(GroupRead).where(GroupRead.group_id == group_id))
    await db.execute(delete(GroupMember).where(GroupMember.group_id == group_id))
    await db.execute(
        delete(UserConversationSetting).where(
            UserConversationSetting.kind == "group",
            UserConversationSetting.key == str(group_id),
        )
    )
    await db.execute(delete(Group).where(Group.id == group_id))
    await db.commit()
    return payload, subs


async def set_avatar(
    db: AsyncSession, me_sub: str, group_id: int, url: str
) -> dict[str, Any]:
    await _require_role(db, group_id, me_sub, {"owner", "admin"})
    prefix = "/api/uploads/"
    if not url.startswith(prefix):
        raise HTTPException(status_code=422, detail="invalid avatar url")
    upload = await get_upload(db, url[len(prefix) :])
    if upload.owner_sub != me_sub:
        raise HTTPException(status_code=403, detail="avatar must be your upload")
    if not upload.mime.startswith("image/"):
        raise HTTPException(status_code=422, detail="avatar must be an image")
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    group.avatar_url = url
    await db.commit()
    return await group_payload(db, group)
