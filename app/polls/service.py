from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.groups.service import membership
from app.models import Poll, PollVote
from app.timeutil import iso_utc

POLL_QUESTION_MAX = 120
POLL_OPTIONS_MIN = 2
POLL_OPTIONS_MAX = 10
POLL_OPTION_MAX = 60


def _validate_poll_input(question: str, options: list[str]) -> list[str]:
    cleaned_question = question.strip()
    if not cleaned_question or len(cleaned_question) > POLL_QUESTION_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"question must be 1-{POLL_QUESTION_MAX} characters",
        )
    cleaned_options: list[str] = []
    for option in options:
        stripped = option.strip()
        if not stripped or len(stripped) > POLL_OPTION_MAX:
            raise HTTPException(
                status_code=422,
                detail=f"each option must be 1-{POLL_OPTION_MAX} characters",
            )
        if stripped not in cleaned_options:
            cleaned_options.append(stripped)
    if len(cleaned_options) < POLL_OPTIONS_MIN:
        raise HTTPException(
            status_code=422,
            detail=f"at least {POLL_OPTIONS_MIN} distinct options",
        )
    if len(cleaned_options) > POLL_OPTIONS_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"at most {POLL_OPTIONS_MAX} options",
        )
    return cleaned_options


async def create_poll(
    db: AsyncSession,
    creator_sub: str,
    group_id: int,
    question: str,
    options: list[str],
    *,
    multiple: bool = False,
) -> Poll:
    if await membership(db, group_id, creator_sub) is None:
        raise HTTPException(status_code=403, detail="not a group member")
    cleaned = _validate_poll_input(question, options)
    poll = Poll(
        group_id=group_id,
        creator_sub=creator_sub,
        question=question.strip(),
        options=json.dumps(cleaned, ensure_ascii=False),
        multiple=multiple,
    )
    db.add(poll)
    await db.flush()
    return poll


async def get_poll(db: AsyncSession, group_id: int, poll_id: int) -> Poll:
    poll = await db.get(Poll, poll_id)
    if poll is None or poll.group_id != group_id:
        raise HTTPException(status_code=404, detail="poll not found")
    return poll


async def poll_payload(db: AsyncSession, poll: Poll, viewer_sub: str) -> dict[str, Any]:
    rows = (
        await db.execute(select(PollVote).where(PollVote.poll_id == poll.id))
    ).scalars().all()
    options = json.loads(poll.options)
    counts: dict[int, int] = {}
    my_votes: list[int] = []
    for row in rows:
        indexes = json.loads(row.option_indexes)
        for index in indexes:
            if isinstance(index, int):
                counts[index] = counts.get(index, 0) + 1
        if row.user_sub == viewer_sub:
            my_votes = [index for index in indexes if isinstance(index, int)]
    return {
        "id": poll.id,
        "question": poll.question,
        "options": [
            {"index": index, "text": text, "count": counts.get(index, 0)}
            for index, text in enumerate(options)
        ],
        "multiple": poll.multiple,
        "closed": poll.closed,
        "total_votes": len(rows),
        "my_votes": sorted(set(my_votes)),
        "creator_sub": poll.creator_sub,
        "created_at": iso_utc(poll.created_at),
    }


async def vote(
    db: AsyncSession,
    me_sub: str,
    group_id: int,
    poll_id: int,
    option_indexes: list[int],
) -> Poll:
    if await membership(db, group_id, me_sub) is None:
        raise HTTPException(status_code=404, detail="group not found")
    poll = await get_poll(db, group_id, poll_id)
    if poll.closed:
        raise HTTPException(status_code=409, detail="poll is closed")
    options = json.loads(poll.options)
    cleaned = sorted(set(option_indexes))
    if any(index < 0 or index >= len(options) for index in cleaned):
        raise HTTPException(status_code=422, detail="invalid option index")
    if not cleaned:
        raise HTTPException(status_code=422, detail="at least one option required")
    if not poll.multiple and len(cleaned) > 1:
        raise HTTPException(status_code=422, detail="poll does not allow multiple choices")
    row = await db.get(PollVote, (poll_id, me_sub))
    if row is None:
        db.add(
            PollVote(
                poll_id=poll_id,
                user_sub=me_sub,
                option_indexes=json.dumps(cleaned),
            )
        )
    else:
        row.option_indexes = json.dumps(cleaned)
    await db.commit()
    await db.refresh(poll)
    return poll


async def close_poll(
    db: AsyncSession, me_sub: str, group_id: int, poll_id: int
) -> Poll:
    member_row = await membership(db, group_id, me_sub)
    if member_row is None:
        raise HTTPException(status_code=404, detail="group not found")
    poll = await get_poll(db, group_id, poll_id)
    if poll.creator_sub != me_sub and member_row.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="only creator or managers can close")
    poll.closed = True
    await db.commit()
    await db.refresh(poll)
    return poll
