from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.timeutil import utcnow


class User(Base):
    __tablename__ = "users"

    sub: Mapped[str] = mapped_column(String(64), primary_key=True)
    nickname: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(128))
    picture: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(255))
    email_verified: Mapped[bool | None] = mapped_column(Boolean)
    bio: Mapped[str | None] = mapped_column(String(200))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AuthState(Base):
    __tablename__ = "auth_states"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    verifier: Mapped[str] = mapped_column(Text)
    nonce: Mapped[str] = mapped_column(String(128))
    redirect_after: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    sid: Mapped[str | None] = mapped_column(String(128))
    acr: Mapped[str | None] = mapped_column(String(128))
    id_token: Mapped[str | None] = mapped_column(Text)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime)


class Friendship(Base):
    __tablename__ = "friendships"

    requester_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )
    addressee_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending")
    remark: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint("requester_sub != addressee_sub", name="ck_friendships_no_self"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    sender_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    recipient_sub: Mapped[str] = mapped_column(ForeignKey("users.sub", ondelete="CASCADE"))
    participant_lo: Mapped[str] = mapped_column(String(64))
    participant_hi: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    conversation_type: Mapped[str] = mapped_column(String(8), default="dm")
    group_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("groups.id", ondelete="CASCADE"),
    )
    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("messages.id", ondelete="SET NULL"),
    )
    content_type: Mapped[str] = mapped_column(String(16), default="text")
    forwarded: Mapped[bool] = mapped_column(Boolean, default=False)
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment_size: Mapped[int | None] = mapped_column(Integer)
    attachment_mime: Mapped[str | None] = mapped_column(String(64))
    attachment_url: Mapped[str | None] = mapped_column(String(255))
    poll_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("polls.id", ondelete="SET NULL"),
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("sender_sub != recipient_sub", name="ck_messages_no_self"),
        CheckConstraint("participant_lo < participant_hi", name="ck_messages_participant_order"),
        Index("ix_messages_conversation", "participant_lo", "participant_hi", "id"),
        Index("ix_messages_group", "group_id", "id"),
    )


class DmRead(Base):
    __tablename__ = "dm_reads"

    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )
    participant_lo: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_hi: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_read_message_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), default=0
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint("participant_lo < participant_hi", name="ck_dm_reads_pair_order"),
    )


class Reaction(Base):
    __tablename__ = "reactions"

    message_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )
    emoji: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MessageMention(Base):
    __tablename__ = "message_mentions"

    message_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )


class UserStar(Base):
    __tablename__ = "user_stars"

    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UserConversationSetting(Base):
    __tablename__ = "user_conversation_settings"

    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    caller_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    callee_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(8))
    status: Mapped[str | None] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(String(64))
    owner_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    announcement: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), default="member")
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')", name="ck_group_members_role"
        ),
    )


class GroupRead(Base):
    __tablename__ = "group_reads"

    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_read_message_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), default=0
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Poll(Base):
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("groups.id", ondelete="CASCADE"),
        index=True,
    )
    creator_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(String(120))
    options: Mapped[str] = mapped_column(Text)
    multiple: Mapped[bool] = mapped_column(Boolean, default=False)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PollVote(Base):
    __tablename__ = "poll_votes"

    poll_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("polls.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True, index=True
    )
    option_indexes: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32))
    actor_sub: Mapped[str | None] = mapped_column(String(64))
    group_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite")
    )
    payload: Mapped[str] = mapped_column(Text, default="{}")
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    owner_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
