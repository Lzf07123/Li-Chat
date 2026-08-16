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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("sender_sub != recipient_sub", name="ck_messages_no_self"),
        CheckConstraint("participant_lo < participant_hi", name="ck_messages_participant_order"),
        Index("ix_messages_conversation", "participant_lo", "participant_hi", "id"),
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
