# 好友与单聊功能实施计划（里程碑二）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 SSO 身份体系上实现小圈子好友关系（搜索/申请/接受/拒绝/解除）与一对一纯文本实时聊天（落库 + WS 双向推送 + 历史分页拉取）。

**Architecture:** REST 是权威写入路径（好友操作与发消息，沿用会话鉴权 + CSRF），落库成功后由服务端经既有 `ConnectionManager` 把消息/好友事件经 WS 推给相关用户；历史消息按 `(participant_lo, participant_hi, id)` 索引倒序游标分页。前端 `static/app.js` 的 AppShell 改为双栏（好友/申请侧栏 + 聊天面板）。

**Tech Stack:** FastAPI、SQLAlchemy 2.0（async，SQLite dev）、原生 JS/CSS 同源前端、pytest + httpx ASGITransport（零外网）。

## Global Constraints

- Python ≥3.12；不新增任何运行时/开发依赖；标识 `Li&Chat` / `lichat`，CSS 前缀 `chat`。
- 全部新 REST 端点会话鉴权（`get_current_user`）；POST/DELETE 加 `require_csrf`；错误码沿用：401 未登录、403 未授权/CSRF、404 不存在、409 冲突、422 校验失败。
- 契约常量（spec §2/§4）：消息内容 1–2000 字符（strip 后校验）；搜索 `q` 1–64 字符、结果 ≤20；历史 `limit` 默认 50、1–100；时间序列化一律 `iso_utc`（naive UTC + `Z`）。
- 测试零外网：`httpx.ASGITransport` + `pytest.ini` 的 `asyncio_mode = auto`；WS 测试用 `starlette.testclient.TestClient`（参考 `tests/test_ws.py` 的会话种子模式）。
- 验证命令（本机 `.venv/bin/*` shebang 指向旧路径，必须用 `python -m`）：
  - `UV_CACHE_DIR=/private/tmp/uv-cache uv sync --group dev`
  - `UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest -q`
  - `UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/ruff check .`
  - `UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m mypy app`
- 提交消息 `<type>: <中文简述>`，每个 Task 独立提交；实现代码在 `codex/friends-dm` 分支（worktree），文档规格/计划已先行提交 main。
- 本环境 git 写操作需用户授权（沙箱对 `.git` 只读），执行时用 `require_escalated` 请求。
- UI：令牌只在 `static/style.css`，品牌文案只在 `static/brand.js`（本功能不改 brand.js）；图标用内联 SVG 禁 emoji；焦点可见、可点击 ≥44px、`sr-only` 标签、消息区 aria-live、尊重 `prefers-reduced-motion`。

---

## Task 0: 隔离工作区（branch + worktree）

**Files:**
- Create: `.worktrees/friends-dm/`（git worktree，无需提交）

- [ ] **Step 1: 创建 worktree 与分支**

```bash
git worktree add .worktrees/friends-dm -b codex/friends-dm
cd .worktrees/friends-dm
git log --oneline -3
```

预期：新分支 `codex/friends-dm`，HEAD 包含规格提交 `621f11e docs: 好友与单聊设计规格（里程碑二）`。

- [ ] **Step 2: 基线验证（后续每 Task 都以此为参考）**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv sync --group dev
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest -q   # 预期 72 passed
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/ruff check .
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m mypy app
```

后续所有 Task 在 `.worktrees/friends-dm/` 内执行。

## Task 1: 好友关系与消息数据模型

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `Base`（`app/db.py`）、`utcnow`（`app/timeutil.py`）。
- Produces:
  - `Friendship(requester_sub, addressee_sub, status, created_at, updated_at)`；复合主键 `(requester_sub, addressee_sub)`，CHECK `requester_sub != addressee_sub`。
  - `Message(id, sender_sub, recipient_sub, participant_lo, participant_hi, content, created_at)`；CHECK `sender_sub != recipient_sub`、`participant_lo < participant_hi`；索引 `ix_messages_conversation (participant_lo, participant_hi, id)`。

- [ ] **Step 1: 写失败测试（追加到 tests/test_models.py 末尾）**

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Friendship, Message


async def test_friendship_roundtrip(db_session: AsyncSession) -> None:
    db_session.add_all([User(sub="u-1", nickname="Alice"), User(sub="u-2", nickname="Bob")])
    await db_session.flush()
    db_session.add(Friendship(requester_sub="u-1", addressee_sub="u-2", status="pending"))
    await db_session.commit()
    row = (
        await db_session.execute(
            select(Friendship).where(Friendship.requester_sub == "u-1")
        )
    ).scalar_one()
    assert row.addressee_sub == "u-2"
    assert row.status == "pending"
    assert row.created_at is not None


async def test_friendship_self_pair_rejected(db_session: AsyncSession) -> None:
    db_session.add(User(sub="u-1", nickname="Alice"))
    await db_session.flush()
    db_session.add(Friendship(requester_sub="u-1", addressee_sub="u-1", status="pending"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_message_roundtrip(db_session: AsyncSession) -> None:
    db_session.add_all([User(sub="u-1", nickname="Alice"), User(sub="u-2", nickname="Bob")])
    await db_session.flush()
    db_session.add(
        Message(
            sender_sub="u-1",
            recipient_sub="u-2",
            participant_lo="u-1",
            participant_hi="u-2",
            content="hello",
        )
    )
    await db_session.commit()
    row = (await db_session.execute(select(Message))).scalar_one()
    assert row.id is not None
    assert row.sender_sub == "u-1"
    assert row.content == "hello"
    assert row.created_at is not None


async def test_message_participant_order_rejected(db_session: AsyncSession) -> None:
    db_session.add_all([User(sub="u-1", nickname="Alice"), User(sub="u-2", nickname="Bob")])
    await db_session.flush()
    db_session.add(
        Message(
            sender_sub="u-1",
            recipient_sub="u-2",
            participant_lo="u-2",
            participant_hi="u-1",
            content="bad order",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
```

注意：`tests/test_models.py` 顶部现有导入 `select`、`AsyncSession`、`User`、`utcnow` 保持不变；新增导入放在 `from app.models import ...` 同一行（`AuthState, Friendship, Message, Session, User`）。

- [ ] **Step 2: 运行测试确认失败**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_models.py -q
```

预期：FAIL（`ImportError: cannot import name 'Friendship' from 'app.models'`）。

- [ ] **Step 3: 实现模型**

修改 `app/models.py`：导入行改为

```python
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
```

文件末尾追加：

```python
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "requester_sub != addressee_sub", name="ck_friendships_no_self"
        ),
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
    recipient_sub: Mapped[str] = mapped_column(
        ForeignKey("users.sub", ondelete="CASCADE")
    )
    participant_lo: Mapped[str] = mapped_column(String(64))
    participant_hi: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("sender_sub != recipient_sub", name="ck_messages_no_self"),
        CheckConstraint(
            "participant_lo < participant_hi", name="ck_messages_participant_order"
        ),
        Index("ix_messages_conversation", "participant_lo", "participant_hi", "id"),
    )
```

> 实现备注：SQLite 的 `BIGINT PRIMARY KEY` 不会自动生成 rowid（插入报 NOT NULL），故用 `BigInteger().with_variant(Integer, "sqlite")`——SQLite 走自增 `INTEGER`，PostgreSQL 保持 `BIGINT`（`Integer` 需加入 models 导入）。

- [ ] **Step 4: 运行测试确认通过**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_models.py -q
```

预期：PASS（原有用例 + 4 个新用例全绿）。

- [ ] **Step 5: 提交**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: 好友关系与消息数据模型"
```

## Task 2: 好友服务基座、时间序列化与用户搜索

**Files:**
- Create: `app/friends/__init__.py`、`app/friends/service.py`
- Modify: `app/timeutil.py`、`app/api/users.py`
- Test: `tests/fixtures/chat.py`、`tests/test_timeutil.py`、`tests/test_friends.py`

**Interfaces:**
- Consumes: `User`、`Friendship`（Task 1）；`AsyncSession`。
- Produces:
  - `app/timeutil.py::iso_utc(dt: datetime) -> str`（naive UTC → `...Z`）。
  - `app/friends/service.py`：`SEARCH_RESULT_LIMIT = 20`；`profile(user) -> dict`；`friend_status(db, me_sub, other_sub) -> str`（`none|incoming|outgoing|friends`）；`search_users(db, me_sub, query, *, limit=20) -> list[dict]`（结果含 `friend_status`，不回传 email）。
  - `GET /api/users/search?q=`（`q` 1–64）。
  - 测试助手 `tests/fixtures/chat.py`：`seed_user`、`seed_session`、`seed_session_sync`、`make_friends`、`make_friends_sync`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_timeutil.py`：

```python
from datetime import UTC, datetime

from app.timeutil import iso_utc


def test_iso_utc_appends_z_to_naive_utc() -> None:
    assert iso_utc(datetime(2026, 8, 16, 12, 0, 0)) == "2026-08-16T12:00:00Z"


def test_iso_utc_normalizes_aware_datetime() -> None:
    aware = datetime(2026, 8, 16, 20, 0, 0, tzinfo=UTC)
    assert iso_utc(aware) == "2026-08-16T20:00:00Z"
```

创建 `tests/fixtures/chat.py`：

```python
from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import create_session
from app.models import Friendship, User


async def seed_user(
    db: AsyncSession,
    sub: str,
    *,
    nickname: str | None = None,
    email: str | None = None,
) -> User:
    user = await db.get(User, sub)
    if user is None:
        user = User(sub=sub, nickname=nickname, email=email)
        db.add(user)
        await db.commit()
    return user


async def seed_session(app: Any, sub: str) -> tuple[str, str]:
    """种子用户 + 会话，返回 (session_id, csrf_token)。"""
    async with app.state.session_factory() as db:
        await seed_user(db, sub)
        session = await create_session(db, sub)
        return session.id, session.csrf_token


async def make_friends(db: AsyncSession, a: str, b: str) -> None:
    await seed_user(db, a, nickname=a)
    await seed_user(db, b, nickname=b)
    db.add(Friendship(requester_sub=a, addressee_sub=b, status="accepted"))
    await db.commit()


def seed_session_sync(app: Any, sub: str) -> tuple[str, str]:
    return asyncio.run(seed_session(app, sub))


def make_friends_sync(app: Any, a: str, b: str) -> None:
    async def run() -> None:
        async with app.state.session_factory() as db:
            await make_friends(db, a, b)

    asyncio.run(run())
```

创建 `tests/test_friends.py`（本 Task 只有搜索部分）：

```python
from __future__ import annotations

from typing import Any

import httpx

from app.models import Friendship
from tests.fixtures.chat import seed_session, seed_user


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def test_search_matches_nickname_or_email_without_leaking_email(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-me", nickname="Me", email="me@example.com")
        await seed_user(db, "u-alice", nickname="Alice", email="alice@example.com")
        await seed_user(db, "u-bob", nickname="Bob", email="bob@example.com")
    client, _ = await _client_for(app, "u-me")
    async with client:
        response = await client.get("/api/users/search", params={"q": "alice"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert [item["sub"] for item in results] == ["u-alice"]
    assert "email" not in results[0]

    client, _ = await _client_for(app, "u-me")
    async with client:
        response = await client.get("/api/users/search", params={"q": "bob@"})
    assert response.status_code == 200
    assert [item["sub"] for item in response.json()["results"]] == ["u-bob"]


async def test_search_reports_friend_status(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-me", nickname="u-me")
        await seed_user(db, "u-friend", nickname="u-friend")
        await seed_user(db, "u-in", nickname="u-in")
        await seed_user(db, "u-out", nickname="u-out")
        db.add_all(
            [
                Friendship(requester_sub="u-me", addressee_sub="u-friend", status="accepted"),
                Friendship(requester_sub="u-in", addressee_sub="u-me", status="pending"),
                Friendship(requester_sub="u-me", addressee_sub="u-out", status="pending"),
            ]
        )
        await db.commit()
    client, _ = await _client_for(app, "u-me")
    async with client:
        response = await client.get("/api/users/search", params={"q": "u-"})
    assert response.status_code == 200
    status_by_sub = {item["sub"]: item["friend_status"] for item in response.json()["results"]}
    assert status_by_sub["u-friend"] == "friends"
    assert status_by_sub["u-in"] == "incoming"
    assert status_by_sub["u-out"] == "outgoing"


async def test_search_rejects_blank_or_long_query(app: Any) -> None:
    client, _ = await _client_for(app, "u-me")
    async with client:
        blank = await client.get("/api/users/search", params={"q": ""})
        too_long = await client.get("/api/users/search", params={"q": "x" * 65})
    assert blank.status_code == 422
    assert too_long.status_code == 422


async def test_search_requires_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/users/search", params={"q": "x"})
    assert response.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_timeutil.py tests/test_friends.py -q
```

预期：FAIL（`iso_utc`、`app.friends.service` 不存在 / 404）。

- [ ] **Step 3: 实现 iso_utc 与好友服务**

`app/timeutil.py` 末尾追加：

```python
def iso_utc(dt: datetime) -> str:
    """naive UTC → ISO8601 字符串（带 Z），供 API/WS 序列化。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat() + "Z"
```

创建 `app/friends/__init__.py`（空文件），创建 `app/friends/service.py`：

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Friendship, User

SEARCH_RESULT_LIMIT = 20


def profile(user: User) -> dict[str, str | None]:
    return {
        "sub": user.sub,
        "nickname": user.nickname,
        "name": user.name,
        "picture": user.picture,
    }


async def _pair_row(db: AsyncSession, a: str, b: str) -> Friendship | None:
    return (
        await db.execute(
            select(Friendship).where(
                or_(
                    and_(Friendship.requester_sub == a, Friendship.addressee_sub == b),
                    and_(Friendship.requester_sub == b, Friendship.addressee_sub == a),
                )
            )
        )
    ).scalar_one_or_none()


async def friend_status(db: AsyncSession, me_sub: str, other_sub: str) -> str:
    row = await _pair_row(db, me_sub, other_sub)
    if row is None:
        return "none"
    if row.status == "accepted":
        return "friends"
    return "outgoing" if row.requester_sub == me_sub else "incoming"


async def search_users(
    db: AsyncSession,
    me_sub: str,
    query: str,
    *,
    limit: int = SEARCH_RESULT_LIMIT,
) -> list[dict[str, Any]]:
    pattern = f"%{query}%"
    users = (
        await db.execute(
            select(User)
            .where(User.sub != me_sub)
            .where(or_(User.nickname.ilike(pattern), User.email.ilike(pattern)))
            .order_by(User.nickname, User.sub)
            .limit(limit)
        )
    ).scalars().all()
    return [
        {**profile(user), "friend_status": await friend_status(db, me_sub, user.sub)}
        for user in users
    ]
```

（Task 2 只落上述四个函数与最小导入；Task 3 补 `HTTPException`/`iso_utc`，Task 4 补 `utcnow`，避免 ruff 未使用导入告警。）

- [ ] **Step 4: 增加搜索路由**

修改 `app/api/users.py`：导入区改为

```python
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.friends import service as friends_service
from app.models import Session, User
```

`MeOut` 之后追加：

```python
class SearchResultOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None
    friend_status: str


class SearchOut(BaseModel):
    results: list[SearchResultOut]
```

`me` 路由之后追加：

```python
@router.get("/users/search", response_model=SearchOut)
async def search_users(
    q: Annotated[str, Query(min_length=1, max_length=64)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchOut:
    results = await friends_service.search_users(db, user.sub, q)
    return SearchOut(results=results)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_timeutil.py tests/test_friends.py -q
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/ruff check .
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m mypy app
```

预期：全绿。

- [ ] **Step 6: 提交**

```bash
git add app/timeutil.py app/friends app/api/users.py tests/fixtures/chat.py tests/test_timeutil.py tests/test_friends.py
git commit -m "feat: 好友服务基座与用户搜索接口"
```

## Task 3: 好友申请发送、列表与实时通知

**Files:**
- Modify: `app/friends/service.py`
- Create: `app/api/friends.py`
- Modify: `app/main.py`
- Test: `tests/test_friends.py`

**Interfaces:**
- Consumes: Task 2 的 `profile`/`_pair_row`、`iso_utc`、测试助手。
- Produces:
  - `service.send_request(db, requester_sub, addressee_sub) -> Friendship`（400 自加 / 404 未知 / 409 已好友·已申请·对方已申请）。
  - `service.list_requests(db, me_sub) -> dict`（`{"incoming":[{"requester":Profile,"created_at"}], "outgoing":[{"addressee":Profile,"created_at"}]}`）。
  - `GET /api/friends/requests`、`POST /api/friends/requests`（201）；POST 成功后向被申请人推 `request_received`。

- [ ] **Step 1: 写失败测试（追加到 tests/test_friends.py）**

```python
from starlette.testclient import TestClient

from tests.fixtures.chat import seed_session, seed_session_sync, seed_user


async def test_send_request_ok(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-bob"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["requester_sub"] == "u-alice"
    assert body["addressee_sub"] == "u-bob"
    assert body["status"] == "pending"
    assert body["created_at"].endswith("Z")


async def test_send_request_to_self_rejected(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-alice"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 400


async def test_send_request_unknown_user_404(app: Any) -> None:
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-ghost"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 404


async def test_send_request_conflicts_409(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
        await seed_user(db, "u-carol", nickname="Carol")
        db.add_all(
            [
                Friendship(requester_sub="u-alice", addressee_sub="u-bob", status="pending"),
                Friendship(requester_sub="u-carol", addressee_sub="u-alice", status="pending"),
            ]
        )
        await db.commit()
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        resend = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-bob"},
            headers={"x-csrf-token": csrf},
        )
        incoming = await client.post(
            "/api/friends/requests",
            json={"to_sub": "u-carol"},
            headers={"x-csrf-token": csrf},
        )
    assert resend.status_code == 409
    assert incoming.status_code == 409


async def test_requests_list_shapes(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
        await seed_user(db, "u-carol", nickname="Carol")
        db.add_all(
            [
                Friendship(requester_sub="u-alice", addressee_sub="u-bob", status="pending"),
                Friendship(requester_sub="u-carol", addressee_sub="u-alice", status="pending"),
            ]
        )
        await db.commit()
    client, _ = await _client_for(app, "u-alice")
    async with client:
        response = await client.get("/api/friends/requests")
    assert response.status_code == 200
    body = response.json()
    assert [item["requester"]["sub"] for item in body["incoming"]] == ["u-carol"]
    assert [item["addressee"]["sub"] for item in body["outgoing"]] == ["u-bob"]
    assert body["incoming"][0]["created_at"].endswith("Z")


async def test_send_request_requires_csrf(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
    client, _ = await _client_for(app, "u-alice")
    async with client:
        response = await client.post("/api/friends/requests", json={"to_sub": "u-bob"})
    assert response.status_code == 403


def test_request_received_pushed_over_ws(app: Any) -> None:
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            response = client.post(
                "/api/friends/requests",
                json={"to_sub": "u-bob"},
                headers={"x-csrf-token": alice_csrf},
            )
            assert response.status_code == 201
            event = ws.receive_json()
    assert event["type"] == "friend_event"
    assert event["event"] == "request_received"
    assert event["by_sub"] == "u-alice"
    assert event["at"].endswith("Z")
```

注意：Task 2 已建 `tests/test_friends.py`，本 Task 的导入按上面新增块补齐（`TestClient` 与 `seed_session_sync` 为新增；`seed_session`、`seed_user`、`Friendship`、`_client_for` 已存在，无需重复）。

- [ ] **Step 2: 运行测试确认失败**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_friends.py -q
```

预期：新用例 FAIL（`send_request`/`list_requests` 不存在；`/api/friends/*` 404）。

- [ ] **Step 3: 实现服务（app/friends/service.py 扩展）**

导入区改为（在 Task 2 版本基础上新增 `HTTPException` 与 `iso_utc`；`utcnow` 留待 Task 4）：

```python
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Friendship, User
from app.timeutil import iso_utc
```

`search_users` 之后追加：

```python
async def send_request(
    db: AsyncSession, requester_sub: str, addressee_sub: str
) -> Friendship:
    if requester_sub == addressee_sub:
        raise HTTPException(status_code=400, detail="cannot send friend request to yourself")
    if await db.get(User, addressee_sub) is None:
        raise HTTPException(status_code=404, detail="user not found")
    existing = await _pair_row(db, requester_sub, addressee_sub)
    if existing is not None:
        if existing.status == "accepted":
            raise HTTPException(status_code=409, detail="already friends")
        if existing.requester_sub == requester_sub:
            raise HTTPException(status_code=409, detail="friend request already sent")
        raise HTTPException(status_code=409, detail="incoming friend request already exists")
    friendship = Friendship(
        requester_sub=requester_sub, addressee_sub=addressee_sub, status="pending"
    )
    db.add(friendship)
    await db.commit()
    await db.refresh(friendship)
    return friendship


async def list_requests(db: AsyncSession, me_sub: str) -> dict[str, list[dict[str, Any]]]:
    rows = (
        await db.execute(
            select(Friendship)
            .where(Friendship.status == "pending")
            .where(
                or_(
                    Friendship.requester_sub == me_sub,
                    Friendship.addressee_sub == me_sub,
                )
            )
            .order_by(Friendship.created_at.desc())
        )
    ).scalars().all()
    subs = {
        row.requester_sub if row.addressee_sub == me_sub else row.addressee_sub
        for row in rows
    }
    users: dict[str, User] = {}
    if subs:
        found = (await db.execute(select(User).where(User.sub.in_(subs)))).scalars().all()
        users = {user.sub: user for user in found}
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for row in rows:
        if row.requester_sub == me_sub:
            other = users.get(row.addressee_sub)
            if other is not None:
                outgoing.append(
                    {"addressee": profile(other), "created_at": iso_utc(row.created_at)}
                )
        else:
            other = users.get(row.requester_sub)
            if other is not None:
                incoming.append(
                    {"requester": profile(other), "created_at": iso_utc(row.created_at)}
                )
    return {"incoming": incoming, "outgoing": outgoing}
```

- [ ] **Step 4: 实现路由（创建 app/api/friends.py）**

```python
from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.friends import service
from app.models import User
from app.timeutil import iso_utc
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/friends", tags=["friends"])


class ProfileOut(BaseModel):
    sub: str
    nickname: str | None = None
    name: str | None = None
    picture: str | None = None


class FriendRequestIn(BaseModel):
    to_sub: str


class FriendRequestOut(BaseModel):
    requester_sub: str
    addressee_sub: str
    status: str
    created_at: str


class IncomingRequestOut(BaseModel):
    requester: ProfileOut
    created_at: str


class OutgoingRequestOut(BaseModel):
    addressee: ProfileOut
    created_at: str


class RequestsOut(BaseModel):
    incoming: list[IncomingRequestOut]
    outgoing: list[OutgoingRequestOut]


class FriendsOut(BaseModel):
    friends: list[ProfileOut]


class StatusOut(BaseModel):
    status: str


def _manager(request: Request) -> ConnectionManager:
    return cast(ConnectionManager, request.app.state.ws_manager)


@router.get("/requests", response_model=RequestsOut)
async def requests_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestsOut:
    return RequestsOut.model_validate(await service.list_requests(db, user.sub))


@router.post("/requests", response_model=FriendRequestOut, status_code=201)
async def create_request(
    request: Request,
    body: FriendRequestIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> FriendRequestOut:
    friendship = await service.send_request(db, user.sub, body.to_sub)
    await _manager(request).send_to(
        friendship.addressee_sub,
        {
            "type": "friend_event",
            "event": "request_received",
            "by_sub": friendship.requester_sub,
            "at": iso_utc(friendship.created_at),
        },
    )
    return FriendRequestOut(
        requester_sub=friendship.requester_sub,
        addressee_sub=friendship.addressee_sub,
        status=friendship.status,
        created_at=iso_utc(friendship.created_at),
    )
```

（`FriendsOut`/`StatusOut` 本 Task 未用——这是 Task 4 要用的模型。为避免 ruff 未使用告警与「Task 内自洽」，**本 Task 先不定义这两个模型**，Task 4 再补。）

修改 `app/main.py`：在 `from app.api.users import router as users_router` 之后加

```python
from app.api.friends import router as friends_router
```

在 `app.include_router(users_router)` 之后加

```python
app.include_router(friends_router)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_friends.py -q
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/ruff check .
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m mypy app
```

预期：全绿。若 `test_request_received_pushed_over_ws` 在 `client.post` 嵌套 WS 上下文时阻塞，改用一个后台线程持有 WS 连接（`threading.Thread` + `queue.Queue` 收帧），主线程继续发 POST；这是 TestClient portal 重入的已知差异，功能断言不变。

- [ ] **Step 6: 提交**

```bash
git add app/friends/service.py app/api/friends.py app/main.py tests/test_friends.py
git commit -m "feat: 好友申请发送、列表与实时通知"
```

## Task 4: 申请处理、好友列表与解除关系

**Files:**
- Modify: `app/friends/service.py`、`app/api/friends.py`
- Test: `tests/test_friends.py`

**Interfaces:**
- Consumes: Task 3 的模型与路由。
- Produces:
  - `service.accept_request(db, me_sub, from_sub) -> Friendship`（仅被申请人，否则 404）。
  - `service.reject_request(db, me_sub, from_sub) -> None`（同上）。
  - `service.list_friends(db, me_sub) -> list[Profile]`（按 `updated_at` 倒序）。
  - `service.remove_relationship(db, me_sub, other_sub) -> Friendship | None`。
  - `service.are_friends(db, a, b) -> bool`（Task 5 使用）。
  - `GET /api/friends`、`POST /api/friends/requests/{from_sub}/accept`、`POST /api/friends/requests/{from_sub}/reject`、`DELETE /api/friends/{other_sub}`；事件推送 `request_accepted`/`request_rejected` → 申请人、`friend_removed` → 关系另一方。

- [ ] **Step 1: 写失败测试（追加到 tests/test_friends.py）**

```python
import asyncio


async def _seed_pending(app: Any, requester: str, addressee: str) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, requester, nickname=requester)
        await seed_user(db, addressee, nickname=addressee)
        db.add(Friendship(requester_sub=requester, addressee_sub=addressee, status="pending"))
        await db.commit()


async def test_accept_request_ok(app: Any) -> None:
    await _seed_pending(app, "u-bob", "u-alice")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/accept",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    client, _ = await _client_for(app, "u-alice")
    async with client:
        friends = await client.get("/api/friends")
    assert [item["sub"] for item in friends.json()["friends"]] == ["u-bob"]


async def test_accept_reject_only_addressee(app: Any) -> None:
    await _seed_pending(app, "u-bob", "u-alice")
    client, csrf = await _client_for(app, "u-bob")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/accept",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 404
    client, csrf = await _client_for(app, "u-bob")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/reject",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 404


async def test_reject_request_removes_pending(app: Any) -> None:
    await _seed_pending(app, "u-bob", "u-alice")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/friends/requests/u-bob/reject",
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "rejected"}
    client, _ = await _client_for(app, "u-alice")
    async with client:
        requests = await client.get("/api/friends/requests")
    assert requests.json() == {"incoming": [], "outgoing": []}


async def test_remove_friend_and_missing(app: Any) -> None:
    async with app.state.session_factory() as db:
        from tests.fixtures.chat import make_friends

        await make_friends(db, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        removed = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
        missing = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
    assert removed.status_code == 200
    assert removed.json() == {"status": "removed"}
    assert missing.status_code == 404


async def test_remove_requires_csrf(app: Any) -> None:
    client, _ = await _client_for(app, "u-alice")
    async with client:
        response = await client.delete("/api/friends/u-bob")
    assert response.status_code == 403


async def test_remove_outgoing_request_cancels(app: Any) -> None:
    await _seed_pending(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        removed = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
        requests = await client.get("/api/friends/requests")
    assert removed.status_code == 200
    assert requests.json() == {"incoming": [], "outgoing": []}


def _seed_pending_sync(app: Any, requester: str, addressee: str) -> None:
    def run() -> None:
        async def inner() -> None:
            async with app.state.session_factory() as db:
                await seed_user(db, requester, nickname=requester)
                await seed_user(db, addressee, nickname=addressee)
                db.add(
                    Friendship(
                        requester_sub=requester,
                        addressee_sub=addressee,
                        status="pending",
                    )
                )
                await db.commit()

        asyncio.run(inner())

    run()


def test_accepted_and_removed_pushed_over_ws(app: Any) -> None:
    _seed_pending_sync(app, "u-bob", "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            response = client.post(
                "/api/friends/requests/u-bob/accept",
                headers={"x-csrf-token": alice_csrf},
            )
            assert response.status_code == 200
            accepted = ws.receive_json()
            removed = client.delete(
                "/api/friends/u-bob", headers={"x-csrf-token": alice_csrf}
            )
            assert removed.status_code == 200
            friend_removed = ws.receive_json()
    assert accepted["event"] == "request_accepted"
    assert accepted["by_sub"] == "u-alice"
    assert friend_removed["event"] == "friend_removed"
    assert friend_removed["by_sub"] == "u-alice"


def test_reject_pushed_over_ws(app: Any) -> None:
    _seed_pending_sync(app, "u-bob", "u-alice")
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            response = client.post(
                "/api/friends/requests/u-bob/reject",
                headers={"x-csrf-token": alice_csrf},
            )
            assert response.status_code == 200
            rejected = ws.receive_json()
    assert rejected["event"] == "request_rejected"
    assert rejected["by_sub"] == "u-alice"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_friends.py -q
```

预期：新用例 FAIL（`accept_request` 等不存在；`/api/friends` 404）。

- [ ] **Step 3: 实现服务（app/friends/service.py 扩展）**

导入区把 Task 3 的 `from app.timeutil import iso_utc` 改为 `from app.timeutil import iso_utc, utcnow`。

`list_requests` 之后追加：

```python
async def accept_request(db: AsyncSession, me_sub: str, from_sub: str) -> Friendship:
    row = await _pair_row(db, from_sub, me_sub)
    if row is None or row.status != "pending" or row.requester_sub != from_sub:
        raise HTTPException(status_code=404, detail="friend request not found")
    row.status = "accepted"
    row.updated_at = utcnow()
    await db.commit()
    await db.refresh(row)
    return row


async def reject_request(db: AsyncSession, me_sub: str, from_sub: str) -> None:
    row = await _pair_row(db, from_sub, me_sub)
    if row is None or row.status != "pending" or row.requester_sub != from_sub:
        raise HTTPException(status_code=404, detail="friend request not found")
    await db.delete(row)
    await db.commit()


async def list_friends(db: AsyncSession, me_sub: str) -> list[dict[str, str | None]]:
    rows = (
        await db.execute(
            select(Friendship)
            .where(Friendship.status == "accepted")
            .where(
                or_(
                    Friendship.requester_sub == me_sub,
                    Friendship.addressee_sub == me_sub,
                )
            )
            .order_by(Friendship.updated_at.desc())
        )
    ).scalars().all()
    others = [
        row.addressee_sub if row.requester_sub == me_sub else row.requester_sub
        for row in rows
    ]
    users: dict[str, User] = {}
    if others:
        found = (
            await db.execute(select(User).where(User.sub.in_(set(others))))
        ).scalars().all()
        users = {user.sub: user for user in found}
    return [profile(users[sub]) for sub in others if sub in users]


async def remove_relationship(
    db: AsyncSession, me_sub: str, other_sub: str
) -> Friendship | None:
    row = await _pair_row(db, me_sub, other_sub)
    if row is None:
        return None
    await db.delete(row)
    await db.commit()
    return row


async def are_friends(db: AsyncSession, a: str, b: str) -> bool:
    row = await _pair_row(db, a, b)
    return row is not None and row.status == "accepted"
```

- [ ] **Step 4: 实现路由（app/api/friends.py 扩展）**

`FriendRequestIn` 之后补模型：

```python
class FriendsOut(BaseModel):
    friends: list[ProfileOut]


class StatusOut(BaseModel):
    status: str
```

文件末尾追加（`HTTPException`、`utcnow` 加入 fastapi/app.timeutil 导入）：

```python
@router.get("", response_model=FriendsOut)
async def friends_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FriendsOut:
    return FriendsOut(friends=await service.list_friends(db, user.sub))


@router.post("/requests/{from_sub}/accept", response_model=StatusOut)
async def accept_request(
    request: Request,
    from_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    friendship = await service.accept_request(db, user.sub, from_sub)
    await _manager(request).send_to(
        friendship.requester_sub,
        {
            "type": "friend_event",
            "event": "request_accepted",
            "by_sub": friendship.addressee_sub,
            "at": iso_utc(friendship.updated_at),
        },
    )
    return StatusOut(status="accepted")


@router.post("/requests/{from_sub}/reject", response_model=StatusOut)
async def reject_request(
    request: Request,
    from_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    await service.reject_request(db, user.sub, from_sub)
    await _manager(request).send_to(
        from_sub,
        {
            "type": "friend_event",
            "event": "request_rejected",
            "by_sub": user.sub,
            "at": iso_utc(utcnow()),
        },
    )
    return StatusOut(status="rejected")


@router.delete("/{other_sub}", response_model=StatusOut)
async def remove_friend(
    request: Request,
    other_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> StatusOut:
    row = await service.remove_relationship(db, user.sub, other_sub)
    if row is None:
        raise HTTPException(status_code=404, detail="no relationship")
    await _manager(request).send_to(
        other_sub,
        {
            "type": "friend_event",
            "event": "friend_removed",
            "by_sub": user.sub,
            "at": iso_utc(utcnow()),
        },
    )
    return StatusOut(status="removed")
```

- [ ] **Step 5: 运行测试确认通过**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_friends.py -q
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/ruff check .
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m mypy app
```

预期：全绿。

- [ ] **Step 6: 提交**

```bash
git add app/friends/service.py app/api/friends.py tests/test_friends.py
git commit -m "feat: 好友申请处理、好友列表与解除关系"
```

## Task 5: 单聊消息发送、历史分页与实时推送

**Files:**
- Create: `app/messages/__init__.py`、`app/messages/service.py`、`app/api/messages.py`
- Modify: `app/main.py`
- Test: `tests/test_messages.py`

**Interfaces:**
- Consumes: `are_friends`（Task 4）、`iso_utc`、`User`/`Message`（Task 1）、测试助手。
- Produces:
  - `MAX_MESSAGE_LENGTH = 2000`、`HISTORY_DEFAULT_LIMIT = 50`、`HISTORY_MAX_LIMIT = 100`。
  - `service.send_message(db, sender_sub, recipient_sub, content) -> Message`（400 自聊 / 404 未知 / 403 非好友）。
  - `service.history(db, me_sub, other_sub, *, before=None, limit=50) -> (list[Message], next_before: int|None)`（倒序，`before` 不含）。
  - `service.message_payload(message) -> dict`。
  - `POST /api/conversations/{sub}/messages`（201，CSRF，校验 1–2000）、`GET /api/conversations/{sub}/messages`；发送成功后向双方推 `{"type":"message","message":...}`。

- [ ] **Step 1: 写失败测试（创建 tests/test_messages.py）**

```python
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from starlette.testclient import TestClient

from tests.fixtures.chat import (
    make_friends,
    seed_session,
    seed_session_sync,
    seed_user,
)


async def _client_for(app: Any, sub: str) -> tuple[httpx.AsyncClient, str]:
    session_id, csrf_token = await seed_session(app, sub)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    client.cookies.set("lichat_session", session_id)
    return client, csrf_token


async def _make_friends(app: Any, a: str, b: str) -> None:
    async with app.state.session_factory() as db:
        await make_friends(db, a, b)


async def test_send_message_ok(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        response = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "你好 Bob"},
            headers={"x-csrf-token": csrf},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["sender_sub"] == "u-alice"
    assert body["recipient_sub"] == "u-bob"
    assert body["content"] == "你好 Bob"
    assert body["created_at"].endswith("Z")


async def test_send_message_validation_errors(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        blank = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "   "},
            headers={"x-csrf-token": csrf},
        )
        too_long = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "x" * 2001},
            headers={"x-csrf-token": csrf},
        )
        self_message = await client.post(
            "/api/conversations/u-alice/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
        ghost = await client.post(
            "/api/conversations/u-ghost/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
    assert blank.status_code == 422
    assert too_long.status_code == 422
    assert self_message.status_code == 400
    assert ghost.status_code == 404


async def test_send_message_requires_friendship_and_csrf(app: Any) -> None:
    async with app.state.session_factory() as db:
        await seed_user(db, "u-bob", nickname="Bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        no_friend = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
        no_csrf = await client.post(
            "/api/conversations/u-bob/messages", json={"content": "hi"}
        )
    assert no_friend.status_code == 403
    assert no_csrf.status_code == 403


async def test_history_desc_pagination_and_termination(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        for index in range(5):
            response = await client.post(
                "/api/conversations/u-bob/messages",
                json={"content": f"m{index}"},
                headers={"x-csrf-token": csrf},
            )
            assert response.status_code == 201
        first = await client.get(
            "/api/conversations/u-bob/messages", params={"limit": 2}
        )
        page = first.json()
        second = await client.get(
            "/api/conversations/u-bob/messages",
            params={"limit": 2, "before": page["next_before"]},
        )
        page2 = second.json()
        third = await client.get(
            "/api/conversations/u-bob/messages",
            params={"limit": 2, "before": page2["next_before"]},
        )
        page3 = third.json()
    assert [item["content"] for item in page["messages"]] == ["m4", "m3"]
    assert [item["content"] for item in page2["messages"]] == ["m2", "m1"]
    assert [item["content"] for item in page3["messages"]] == ["m0"]
    assert page3["next_before"] is None


async def test_history_visible_after_unfriend_and_stranger_empty(app: Any) -> None:
    await _make_friends(app, "u-alice", "u-bob")
    async with app.state.session_factory() as db:
        await seed_user(db, "u-carol", nickname="Carol")
    client, csrf = await _client_for(app, "u-alice")
    async with client:
        sent = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "留档"},
            headers={"x-csrf-token": csrf},
        )
        assert sent.status_code == 201
        removed = await client.delete(
            "/api/friends/u-bob", headers={"x-csrf-token": csrf}
        )
        assert removed.status_code == 200
        blocked = await client.post(
            "/api/conversations/u-bob/messages",
            json={"content": "hi"},
            headers={"x-csrf-token": csrf},
        )
        history = await client.get("/api/conversations/u-bob/messages")
        stranger = await client.get("/api/conversations/u-carol/messages")
    assert blocked.status_code == 403
    assert history.status_code == 200
    assert [item["content"] for item in history.json()["messages"]] == ["留档"]
    assert stranger.status_code == 200
    assert stranger.json() == {"messages": [], "next_before": None}


async def test_history_parameter_validation(app: Any) -> None:
    client, _ = await _client_for(app, "u-alice")
    async with client:
        zero_limit = await client.get(
            "/api/conversations/u-bob/messages", params={"limit": 0}
        )
        bad_before = await client.get(
            "/api/conversations/u-bob/messages", params={"before": 0}
        )
    assert zero_limit.status_code == 422
    assert bad_before.status_code == 422


async def test_messages_require_session(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/conversations/u-bob/messages")
    assert response.status_code == 401


def test_message_pushed_to_both_parties_over_ws(app: Any) -> None:
    seed_session_sync(app, "u-alice")
    seed_session_sync(app, "u-bob")

    async def run_friends() -> None:
        await _make_friends(app, "u-alice", "u-bob")

    asyncio.run(run_friends())
    bob_sid, _ = seed_session_sync(app, "u-bob")
    alice_sid, alice_csrf = seed_session_sync(app, "u-alice")
    with TestClient(app) as client:
        client.cookies.set("lichat_session", bob_sid)
        with client.websocket_connect("/ws") as bob_ws:
            assert bob_ws.receive_json() == {"type": "hello", "sub": "u-bob"}
            client.cookies.set("lichat_session", alice_sid)
            with client.websocket_connect("/ws") as alice_ws:
                assert alice_ws.receive_json() == {"type": "hello", "sub": "u-alice"}
                response = client.post(
                    "/api/conversations/u-bob/messages",
                    json={"content": "实时"},
                    headers={"x-csrf-token": alice_csrf},
                )
                assert response.status_code == 201
                alice_event = alice_ws.receive_json()
            bob_event = bob_ws.receive_json()
    assert alice_event["type"] == "message"
    assert alice_event["message"]["content"] == "实时"
    assert bob_event["type"] == "message"
    assert bob_event["message"]["content"] == "实时"
    assert bob_event["message"]["id"] == alice_event["message"]["id"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_messages.py -q
```

预期：FAIL（`app.messages.service` 不存在 / 404）。

- [ ] **Step 3: 实现消息服务（创建 app/messages/__init__.py 与 service.py）**

`app/messages/__init__.py` 空文件；`app/messages/service.py`：

```python
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.friends.service import are_friends
from app.models import Message, User
from app.timeutil import iso_utc

MAX_MESSAGE_LENGTH = 2000
HISTORY_DEFAULT_LIMIT = 50
HISTORY_MAX_LIMIT = 100


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def message_payload(message: Message) -> dict[str, str | int]:
    return {
        "id": message.id,
        "sender_sub": message.sender_sub,
        "recipient_sub": message.recipient_sub,
        "content": message.content,
        "created_at": iso_utc(message.created_at),
    }


async def send_message(
    db: AsyncSession, sender_sub: str, recipient_sub: str, content: str
) -> Message:
    if sender_sub == recipient_sub:
        raise HTTPException(status_code=400, detail="cannot message yourself")
    if await db.get(User, recipient_sub) is None:
        raise HTTPException(status_code=404, detail="user not found")
    if not await are_friends(db, sender_sub, recipient_sub):
        raise HTTPException(status_code=403, detail="not friends")
    lo, hi = pair_key(sender_sub, recipient_sub)
    message = Message(
        sender_sub=sender_sub,
        recipient_sub=recipient_sub,
        participant_lo=lo,
        participant_hi=hi,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def history(
    db: AsyncSession,
    me_sub: str,
    other_sub: str,
    *,
    before: int | None = None,
    limit: int = HISTORY_DEFAULT_LIMIT,
) -> tuple[list[Message], int | None]:
    lo, hi = pair_key(me_sub, other_sub)
    stmt = (
        select(Message)
        .where(Message.participant_lo == lo, Message.participant_hi == hi)
        .order_by(Message.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        stmt = stmt.where(Message.id < before)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_before = page[-1].id if has_more and page else None
    return page, next_before
```

- [ ] **Step 4: 实现路由（创建 app/api/messages.py）**

```python
from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.db import get_db
from app.messages import service
from app.messages.service import MAX_MESSAGE_LENGTH
from app.models import User
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/conversations", tags=["messages"])


class MessageIn(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be blank")
        if len(stripped) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"content must be at most {MAX_MESSAGE_LENGTH} characters"
            )
        return stripped


class MessageOut(BaseModel):
    id: int
    sender_sub: str
    recipient_sub: str
    content: str
    created_at: str


class MessagePageOut(BaseModel):
    messages: list[MessageOut]
    next_before: int | None


@router.post("/{other_sub}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    request: Request,
    other_sub: str,
    body: MessageIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MessageOut:
    message = await service.send_message(db, user.sub, other_sub, body.content)
    payload = service.message_payload(message)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    event = {"type": "message", "message": payload}
    await manager.send_to(message.sender_sub, event)
    await manager.send_to(message.recipient_sub, event)
    return MessageOut(**payload)


@router.get("/{other_sub}/messages", response_model=MessagePageOut)
async def message_history(
    other_sub: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=service.HISTORY_MAX_LIMIT)] = service.HISTORY_DEFAULT_LIMIT,
) -> MessagePageOut:
    rows, next_before = await service.history(
        db, user.sub, other_sub, before=before, limit=limit
    )
    return MessagePageOut(
        messages=[MessageOut(**service.message_payload(item)) for item in rows],
        next_before=next_before,
    )
```

修改 `app/main.py`：在 friends router 导入后加

```python
from app.api.messages import router as messages_router
```

在 `app.include_router(friends_router)` 后加

```python
app.include_router(messages_router)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_messages.py -q
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/ruff check .
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m mypy app
```

预期：全绿。若双 WS 嵌套上下文导致 portal 重入问题，改用一个后台线程持有 bob 的 WS（同 Task 3 注记），断言不变。

- [ ] **Step 6: 提交**

```bash
git add app/messages app/api/messages.py app/main.py tests/test_messages.py
git commit -m "feat: 单聊消息发送、历史分页与实时推送"
```

## Task 6: 前端聊天逻辑（static/app.js）

**Files:**
- Modify: `static/app.js`
- Test: `tests/test_frontend.py`

**Interfaces:**
- Consumes: `GET /api/friends`、`GET /api/friends/requests`、`GET /api/users/search`、`POST /api/friends/requests`、`POST /api/friends/requests/{from}/accept|reject`、`DELETE /api/friends/{sub}`、`POST|GET /api/conversations/{sub}/messages`；WS `message`/`friend_event`/`hello`；`BRAND`、`LiChatTheme`、`LiChatAmbient`（现有全局）。
- Produces: 双栏聊天 UI 行为；保留既有契约字符串（`/oidc/login`、`csrf_token`、`4401`、`role="status"`、`LiChatTheme.initTheme`）供 `test_app_script_contracts` 回归。

- [ ] **Step 1: 写失败测试（追加到 tests/test_frontend.py）**

```python
async def test_app_chat_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert "/api/friends" in text
    assert "/api/friends/requests" in text
    assert "/api/users/search" in text
    assert "/api/conversations/" in text
    assert '"message"' in text
    assert "friend_event" in text
    assert "encodeURIComponent" in text
    assert 'role="log"' in text
    assert "textContent" in text
```

- [ ] **Step 2: 运行测试确认失败**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_frontend.py::test_app_chat_contracts -q
```

预期：FAIL（上述字符串均不存在）。

- [ ] **Step 3: 实现 app.js**

保留文件头部 `"use strict";`、`escapeHtml`、`footerHtml`、`themeToggleHtml`、`mount`、`loadMe`、`logout` 不变；`state` 扩展，新增下述函数，并用新的 `renderLoggedIn` 替换旧实现，`connectWebSocket` 增加 `message` 事件监听。完整替换后的文件内容如下（直接整体覆盖 `static/app.js`）：

```javascript
"use strict";

const state = {
  me: null,
  ws: null,
  pingTimer: null,
  friends: [],
  requests: { incoming: [], outgoing: [] },
  searchResults: [],
  activeSub: null,
  activePeer: null,
  messages: [],
  nextBefore: null,
  loadingHistory: false,
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function footerHtml() {
  return `<footer class="site-footer">${escapeHtml(BRAND.footer())}</footer>`;
}

function themeToggleHtml() {
  return `
    <button id="theme-toggle" class="icon-btn theme-toggle" type="button" aria-label="切换主题">
      <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" aria-hidden="true">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
      </svg>
      <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    </button>`;
}

function mount(className, inner) {
  const app = document.getElementById("app");
  app.className = className;
  app.innerHTML = inner;
  LiChatTheme.initTheme();
}

function displayName(user) {
  return user.nickname || user.name || user.sub;
}

function avatarHtml(user) {
  const initial = escapeHtml(displayName(user).slice(0, 1).toUpperCase());
  return user.picture
    ? `<img class="avatar" src="${escapeHtml(user.picture)}" alt="头像" />`
    : `<div class="avatar avatar-placeholder" aria-hidden="true">${initial}</div>`;
}

async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers);
  if (typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }
  if (state.me) headers["X-CSRF-Token"] = state.me.csrf_token;
  let response;
  try {
    response = await fetch(path, Object.assign({}, options, {
      credentials: "same-origin",
      headers,
    }));
  } catch {
    throw new Error("网络错误，请稍后重试");
  }
  if (response.status === 401) {
    window.location.href = "/oidc/login";
    throw new Error("登录已失效");
  }
  return response;
}

async function loadMe() {
  let response;
  try {
    response = await fetch("/api/me", { credentials: "same-origin" });
  } catch {
    renderLoggedOut();
    return;
  }
  if (!response.ok) {
    renderLoggedOut();
    return;
  }
  state.me = await response.json();
  renderLoggedIn();
  connectWebSocket();
}

function renderLoggedOut() {
  window.LiChatAmbient && window.LiChatAmbient.setDensity(10);
  mount(
    "auth-shell",
    `${themeToggleHtml()}
    <div class="auth-brand">${BRAND.logo}<span class="brand-name">${escapeHtml(BRAND.name)}</span></div>
    <p class="slogan">${escapeHtml(BRAND.slogan)}</p>
    <section class="card card-interactive auth-card page-enter">
      <h1>欢迎回来</h1>
      <p class="muted">统一使用 Li&Pass 账号登录，本地不保存密码。</p>
      <a class="btn btn-primary" href="/oidc/login">使用 Li&Pass 登录</a>
    </section>
    ${footerHtml()}`
  );
}

function headerHtml() {
  return `<header class="app-header">
    <div class="app-brand">${BRAND.logo}<span>${escapeHtml(BRAND.name)}</span></div>
    <div class="app-actions">
      ${themeToggleHtml()}
      <button id="logout" class="btn btn-secondary btn-sm" type="button">退出登录</button>
    </div>
  </header>`;
}

function mainHtml() {
  return `<main class="app-main app-main-chat">
    <aside class="chat-sidebar" aria-label="好友与申请">
      <form id="search-form" class="search-box">
        <label class="sr-only" for="search-input">搜索用户</label>
        <input id="search-input" class="input" type="search" maxlength="64"
          placeholder="按昵称或邮箱搜索" autocomplete="off" />
        <button class="btn btn-primary btn-sm" type="submit">搜索</button>
      </form>
      <ul id="search-results" class="contact-list search-results" hidden></ul>
      <section class="sidebar-section">
        <h2 class="sidebar-title">好友申请
          <span id="requests-badge" class="badge badge-primary" hidden>0</span>
        </h2>
        <p id="requests-empty" class="sidebar-empty">暂无申请</p>
        <ul id="requests-list" class="contact-list"></ul>
      </section>
      <section class="sidebar-section">
        <h2 class="sidebar-title">好友</h2>
        <p id="friends-empty" class="sidebar-empty">还没有好友，先搜索添加</p>
        <ul id="friends-list" class="contact-list"></ul>
      </section>
      <div class="ws-status sidebar-status">
        <span id="ws-dot" class="status-dot status-connecting" aria-hidden="true"></span>
        <span id="ws-text" role="status">连接中…</span>
      </div>
    </aside>
    <section id="chat-panel" class="chat-panel" aria-label="聊天">
      <div id="chat-empty" class="chat-empty">
        <p>选择一个好友开始聊天</p>
        <p class="muted">对话只在你们之间流动</p>
      </div>
      <div id="chat-active" class="chat-active" hidden>
        <header class="chat-header">
          <button id="chat-back" class="icon-btn chat-back" type="button" aria-label="返回好友列表">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M15 18l-6-6 6-6"/>
            </svg>
          </button>
          <div class="chat-peer" id="chat-peer"></div>
        </header>
        <div class="messages-wrap">
          <button id="load-older" class="btn btn-ghost btn-sm load-older" type="button" hidden>
            加载更早消息
          </button>
          <div id="messages" class="messages" role="log" aria-live="polite" aria-label="聊天记录"></div>
        </div>
        <form id="composer" class="composer">
          <label class="sr-only" for="message-input">消息内容</label>
          <textarea id="message-input" class="input" rows="1" maxlength="2000"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"></textarea>
          <button class="btn btn-primary" type="submit">发送</button>
        </form>
      </div>
    </section>
  </main>
  ${footerHtml()}`;
}

function renderLoggedIn() {
  window.LiChatAmbient && window.LiChatAmbient.setDensity(8);
  mount("app-shell", `${headerHtml()} ${mainHtml()}`);
  document.getElementById("logout").addEventListener("click", logout);
  document.getElementById("search-form").addEventListener("submit", onSearch);
  document.getElementById("search-results").addEventListener("click", onSearchResultClick);
  document.getElementById("requests-list").addEventListener("click", onRequestListClick);
  document.getElementById("friends-list").addEventListener("click", onFriendListClick);
  document.getElementById("composer").addEventListener("submit", onComposerSubmit);
  document.getElementById("message-input").addEventListener("keydown", onComposerKeydown);
  document.getElementById("load-older").addEventListener("click", loadOlder);
  document.getElementById("chat-back").addEventListener("click", closeChat);
  refreshSidebar();
}

async function refreshSidebar() {
  try {
    const [friendsRes, requestsRes] = await Promise.all([
      api("/api/friends"),
      api("/api/friends/requests"),
    ]);
    if (friendsRes.ok) state.friends = (await friendsRes.json()).friends;
    if (requestsRes.ok) state.requests = await requestsRes.json();
    renderSidebar();
  } catch {
    /* 登录失效已由 api() 统一跳转 */
  }
}

function renderSidebar() {
  const badge = document.getElementById("requests-badge");
  badge.hidden = state.requests.incoming.length === 0;
  badge.textContent = String(state.requests.incoming.length);
  document.getElementById("requests-empty").hidden =
    state.requests.incoming.length + state.requests.outgoing.length > 0;
  document.getElementById("requests-list").innerHTML = [
    ...state.requests.incoming.map(requestIncomingHtml),
    ...state.requests.outgoing.map(requestOutgoingHtml),
  ].join("");
  document.getElementById("friends-empty").hidden = state.friends.length > 0;
  document.getElementById("friends-list").innerHTML = state.friends.map(friendHtml).join("");
}

function requestIncomingHtml(item) {
  return `<li class="contact-item">
    <div class="contact-info">
      ${avatarHtml(item.requester)}
      <span class="contact-name">${escapeHtml(displayName(item.requester))}</span>
    </div>
    <div class="contact-actions">
      <button class="btn btn-primary btn-sm" type="button"
        data-action="accept" data-sub="${escapeHtml(item.requester.sub)}">接受</button>
      <button class="btn btn-ghost btn-sm" type="button"
        data-action="reject" data-sub="${escapeHtml(item.requester.sub)}">拒绝</button>
    </div>
  </li>`;
}

function requestOutgoingHtml(item) {
  return `<li class="contact-item">
    <div class="contact-info">
      ${avatarHtml(item.addressee)}
      <span class="contact-name">${escapeHtml(displayName(item.addressee))}</span>
    </div>
    <button class="btn btn-ghost btn-sm" type="button"
      data-action="cancel" data-sub="${escapeHtml(item.addressee.sub)}">撤回</button>
  </li>`;
}

function friendHtml(friend) {
  return `<li class="contact-item">
    <button class="contact-button" type="button"
      data-action="open" data-sub="${escapeHtml(friend.sub)}">
      ${avatarHtml(friend)}
      <span class="contact-name">${escapeHtml(displayName(friend))}</span>
    </button>
  </li>`;
}

function searchResultHtml(result) {
  const actions = {
    none: `<button class="btn btn-primary btn-sm" type="button"
      data-action="add" data-sub="${escapeHtml(result.sub)}">添加好友</button>`,
    incoming: `<span class="badge badge-warning">待你处理</span>`,
    outgoing: `<span class="badge badge-muted">已申请</span>`,
    friends: `<button class="btn btn-secondary btn-sm" type="button"
      data-action="open" data-sub="${escapeHtml(result.sub)}">发消息</button>`,
  };
  return `<li class="contact-item search-item">
    <div class="contact-info">
      ${avatarHtml(result)}
      <span class="contact-name">${escapeHtml(displayName(result))}</span>
    </div>
    ${actions[result.friend_status] || actions.none}
  </li>`;
}

async function onSearch(event) {
  event.preventDefault();
  const input = document.getElementById("search-input");
  const query = input.value.trim();
  const results = document.getElementById("search-results");
  if (!query) {
    results.hidden = true;
    return;
  }
  const response = await api(`/api/users/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) {
    results.hidden = true;
    return;
  }
  state.searchResults = (await response.json()).results;
  results.hidden = state.searchResults.length === 0;
  results.innerHTML = state.searchResults.map(searchResultHtml).join("");
}

async function onSearchResultClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "open") {
    openChat(button.dataset.sub);
    return;
  }
  const response = await api("/api/friends/requests", {
    method: "POST",
    body: JSON.stringify({ to_sub: button.dataset.sub }),
  });
  if (response.ok || response.status === 409) {
    await refreshSidebar();
    document.getElementById("search-input").value = "";
    document.getElementById("search-results").hidden = true;
  }
}

async function onRequestListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const sub = button.dataset.sub;
  if (button.dataset.action === "accept") {
    await api(`/api/friends/requests/${encodeURIComponent(sub)}/accept`, { method: "POST" });
  } else if (button.dataset.action === "reject") {
    await api(`/api/friends/requests/${encodeURIComponent(sub)}/reject`, { method: "POST" });
  } else if (button.dataset.action === "cancel") {
    await api(`/api/friends/${encodeURIComponent(sub)}`, { method: "DELETE" });
  }
  await refreshSidebar();
}

function onFriendListClick(event) {
  const button = event.target.closest("[data-action='open']");
  if (!button) return;
  openChat(button.dataset.sub);
}

async function openChat(sub) {
  const peer =
    state.friends.find((friend) => friend.sub === sub) ||
    state.searchResults.find((result) => result.sub === sub) ||
    null;
  if (!peer) return;
  state.activeSub = sub;
  state.activePeer = peer;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = true;
  document.getElementById("chat-active").hidden = false;
  document.getElementById("chat-peer").innerHTML = `
    ${avatarHtml(peer)}
    <span class="chat-peer-name">${escapeHtml(displayName(peer))}</span>`;
  document.getElementById("message-input").value = "";
  document.getElementById("load-older").hidden = true;
  renderMessages();
  document.getElementById("app").classList.add("chat-open");
  await loadHistory();
  if (window.innerWidth >= 768) document.getElementById("message-input").focus();
}

async function loadHistory(before) {
  if (state.loadingHistory) return;
  state.loadingHistory = true;
  let url = `/api/conversations/${encodeURIComponent(state.activeSub)}/messages?limit=50`;
  if (before) url += `&before=${before}`;
  try {
    const response = await api(url);
    if (!response.ok) return;
    const page = await response.json();
    state.nextBefore = page.next_before;
    if (before) {
      state.messages = page.messages.slice().reverse().concat(state.messages);
      renderMessages();
    } else {
      state.messages = page.messages.slice().reverse();
      renderMessages();
      const container = document.getElementById("messages");
      container.scrollTop = container.scrollHeight;
    }
    document.getElementById("load-older").hidden = !page.next_before;
  } finally {
    state.loadingHistory = false;
  }
}

function loadOlder() {
  loadHistory(state.nextBefore);
}

function closeChat() {
  state.activeSub = null;
  state.activePeer = null;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = false;
  document.getElementById("chat-active").hidden = true;
  document.getElementById("app").classList.remove("chat-open");
}

function messageHtml(message) {
  const own = message.sender_sub === state.me.sub;
  const time = new Date(message.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `<div class="message ${own ? "message-own" : "message-other"}">
    <div class="message-bubble">${escapeHtml(message.content)}</div>
    <div class="message-meta">${escapeHtml(time)}</div>
  </div>`;
}

function renderMessages() {
  const container = document.getElementById("messages");
  container.innerHTML = state.messages
    .slice()
    .sort((a, b) => a.id - b.id)
    .map(messageHtml)
    .join("");
}

function appendMessage(message) {
  if (state.messages.some((item) => item.id === message.id)) return;
  state.messages.push(message);
  const container = document.getElementById("messages");
  container.insertAdjacentHTML("beforeend", messageHtml(message));
  container.scrollTop = container.scrollHeight;
}

async function onComposerSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("message-input");
  const content = input.value.trim();
  if (!content || !state.activeSub) return;
  const response = await api(
    `/api/conversations/${encodeURIComponent(state.activeSub)}/messages`,
    { method: "POST", body: JSON.stringify({ content }) }
  );
  if (response.ok) {
    input.value = "";
    input.focus();
  }
}

function onComposerKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.getElementById("composer").requestSubmit();
  }
}

function handleServerMessage(data) {
  if (data.type === "message" && data.message) {
    const message = data.message;
    if (
      state.activeSub &&
      (message.sender_sub === state.activeSub || message.recipient_sub === state.activeSub)
    ) {
      appendMessage(message);
    }
  } else if (data.type === "friend_event") {
    refreshSidebar();
  }
}

function logout() {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/oidc/logout";
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = "csrf_token";
  input.value = state.me.csrf_token;
  form.appendChild(input);
  document.body.appendChild(form);
  form.submit();
}

function connectWebSocket() {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${window.location.host}/ws`);
  state.ws = socket;

  function setStatus(kind, text) {
    const dot = document.getElementById("ws-dot");
    const label = document.getElementById("ws-text");
    if (dot) dot.className = `status-dot status-${kind}`;
    if (label) label.textContent = text;
  }

  socket.addEventListener("open", () => setStatus("connected", "已连接"));
  socket.addEventListener("error", () => setStatus("disconnected", "连接已断开"));
  socket.addEventListener("message", (event) => {
    try {
      handleServerMessage(JSON.parse(event.data));
    } catch {
      /* 忽略无法解析的帧 */
    }
  });
  socket.addEventListener("close", (event) => {
    if (event.code === 4401) {
      setStatus("invalid", "登录已失效，正在跳转…");
      window.location.href = "/oidc/login";
      return;
    }
    setStatus("disconnected", "连接已断开");
  });

  state.pingTimer = window.setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, 25000);
}

loadMe();
```

- [ ] **Step 4: 运行测试确认通过**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_frontend.py -q
```

预期：PASS（含原有 `test_app_script_contracts` 回归）。

- [ ] **Step 5: 提交**

```bash
git add static/app.js tests/test_frontend.py
git commit -m "feat: 前端双栏好友与聊天逻辑"
```

## Task 7: 前端聊天样式（static/style.css）

**Files:**
- Modify: `static/style.css`
- Test: `tests/test_frontend.py`

**Interfaces:**
- Consumes: Task 6 的 DOM 结构；既有 `--chat-*` 令牌（bg/surface/surface-2/fg/muted/border/primary/primary-fg）与 `.input/.btn/.badge/.avatar/.status-dot` 组件。
- Produces: `.app-main-chat/.chat-sidebar/.search-box/.search-results/.sidebar-section/.sidebar-title/.sidebar-empty/.contact-list/.contact-item/.contact-button/.contact-info/.contact-name/.contact-actions/.chat-panel/.chat-empty/.chat-active/.chat-header/.chat-peer/.chat-peer-name/.chat-back/.messages-wrap/.load-older/.messages/.message*/.message-bubble/.message-meta/.composer/.sidebar-status/.sr-only` + `<768px` 两态切换。

- [ ] **Step 1: 写失败测试（追加到 tests/test_frontend.py）**

```python
async def test_chat_styles_present(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/style.css")
    assert response.status_code == 200
    text = response.text
    assert ".chat-sidebar" in text
    assert ".chat-panel" in text
    assert ".message-bubble" in text
    assert ".message-own" in text
    assert ".composer" in text
    assert ".sr-only" in text
    assert "max-width: 767px" in text
```

- [ ] **Step 2: 运行测试确认失败**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_frontend.py::test_chat_styles_present -q
```

预期：FAIL（选择器不存在）。

- [ ] **Step 3: 实现样式（追加到 static/style.css 末尾）**

```css
/* ===== 好友与单聊双栏布局（里程碑二） ===== */
.app-main-chat [hidden] {
  display: none !important;
}

.app-main-chat {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  max-width: 1100px;
}

.chat-sidebar {
  position: sticky;
  top: 84px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.search-box {
  display: flex;
  gap: 8px;
}

.search-box .input {
  flex: 1;
  min-width: 0;
}

.search-results,
.sidebar-section {
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
  border-radius: 16px;
  padding: 16px;
}

.search-results[hidden] {
  display: none;
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--chat-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-empty {
  font-size: 0.875rem;
  color: var(--chat-muted);
  margin: 4px 0;
}

.contact-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.contact-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.contact-button {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
  padding: 8px;
  border: none;
  border-radius: 12px;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.contact-button:hover {
  background: var(--chat-surface-2);
}

.contact-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.contact-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contact-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.chat-sidebar .avatar,
.chat-peer .avatar {
  width: 36px;
  height: 36px;
  font-size: 0.875rem;
  flex-shrink: 0;
}

.sidebar-status {
  padding: 4px 8px;
  font-size: 0.875rem;
  color: var(--chat-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-panel {
  position: sticky;
  top: 84px;
  display: flex;
  flex-direction: column;
  height: min(70vh, 640px);
  min-height: 420px;
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
  border-radius: 16px;
  overflow: hidden;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--chat-muted);
}

.chat-active {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-active[hidden] {
  display: none;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--chat-border);
}

.chat-peer {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.chat-peer-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-back {
  display: none;
}

.messages-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.load-older {
  align-self: center;
  margin: 8px 0;
}

.load-older[hidden] {
  display: none;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.message {
  display: flex;
  flex-direction: column;
  max-width: 72%;
}

.message-own {
  align-self: flex-end;
  align-items: flex-end;
}

.message-other {
  align-self: flex-start;
  align-items: flex-start;
}

.message-bubble {
  padding: 8px 12px;
  border-radius: 14px;
  background: var(--chat-surface-2);
  color: var(--chat-fg);
  white-space: pre-wrap;
  word-break: break-word;
}

.message-own .message-bubble {
  background: var(--chat-primary);
  color: var(--chat-primary-fg);
}

.message-meta {
  font-size: 0.75rem;
  color: var(--chat-muted);
  margin-top: 2px;
  padding: 0 4px;
}

.composer {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 12px 16px;
  border-top: 1px solid var(--chat-border);
}

.composer textarea {
  flex: 1;
  min-width: 0;
  min-height: 44px;
  max-height: 120px;
  resize: none;
  font: inherit;
}

.composer .btn {
  flex-shrink: 0;
  min-height: 44px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 767px) {
  .app-main-chat {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }

  .chat-sidebar,
  .chat-panel {
    position: static;
    height: calc(100dvh - 160px);
  }

  .chat-panel {
    display: none;
  }

  .app-shell.chat-open .chat-sidebar {
    display: none;
  }

  .app-shell.chat-open .chat-panel {
    display: flex;
  }

  .chat-back {
    display: inline-flex;
  }
}
```

注意：若 `.avatar` 现有尺寸规则与上面的 36px 覆盖冲突，以「聊天列表/会话头 36px、资料卡保持原尺寸」为验收口径；`dvh` 在不支持的浏览器回退 `vh`（本功能目标浏览器均支持，先不加回退）。

- [ ] **Step 4: 运行测试确认通过**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest tests/test_frontend.py -q
```

预期：PASS。

- [ ] **Step 5: 提交**

```bash
git add static/style.css tests/test_frontend.py
git commit -m "feat: 双栏聊天界面样式（含移动端两态）"
```

## Task 8: 全量验证与文档收尾

**Files:**
- Modify: `CHANGELOG.md`、`README.md`、`docs/architecture.md`、`docs/api.md`、`docs/security.md`

**Interfaces:**
- Consumes: Task 1–7 的全部产物。
- Produces: 与实现一致的四份文档 + 更新后的变更记录。

- [ ] **Step 1: 全量质量门禁**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m pytest -q
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/ruff check .
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m mypy app
```

预期：pytest 全绿（记下实际总数 N）、ruff/mypy 无告警。任何失败先修复再继续（不要带病写文档）。

- [ ] **Step 2: 更新 CHANGELOG.md**

「未发布（开发中）→ 功能」分区追加一条：

```markdown
- 好友与单聊（里程碑二）：昵称/邮箱关键词搜索（不回传邮箱）、申请-同意制好友关系（accept/reject/撤回/解除）、单向解除关系且历史保留、纯文本一对一实时聊天（REST 落库 + WS 双向推送）、历史消息倒序游标分页
```

- [ ] **Step 3: 更新 README.md**

- 「功能」追加两行：`- 好友：按昵称/邮箱搜索、申请与处理、列表与解除` 与 `- 单聊：纯文本实时收发、历史分页拉取（未读/已读与离线推送在下一里程碑）`。
- 「质量门禁」里 `62 个测试` 改为 Step 1 实测的 `N 个测试`。
- 「项目结构」的 `app/` 注释补：`api/           # /api/me、用户搜索、好友与单聊路由`；新增 `friends/` 与 `messages/` 两行注释；`models.py` 注释改为 `users / auth_states / sessions / friendships / messages 五张表`。
- 「路线图」勾选里程碑二：`- [x] 里程碑二：好友关系与一对一实时聊天`。
- 「文档索引」追加：`- [好友与单聊设计规格](docs/superpowers/specs/2026-08-16-friends-dm-design.md)` 与 `- [好友与单聊实施计划](docs/superpowers/plans/2026-08-16-friends-dm.md)`。

- [ ] **Step 4: 更新 docs/architecture.md**

- 模块职责表追加四行：`app/friends/`（好友业务：搜索、关系状态、申请生命周期）、`app/messages/`（消息业务：发送、历史分页、校验）、`app/api/friends.py`（`/api/friends/*` 薄路由）、`app/api/messages.py`（`/api/conversations/*` 薄路由）。
- 数据模型表追加两行：`friendships`（`requester_sub+addressee_sub` 复合主键、`status`(pending/accepted)、时间戳、无自环约束）、`messages`（自增 `id`、`sender/recipient`、`participant_lo/hi` 会话键、`content`、`created_at`，会话索引）。
- 「实时通道」段补一句：除心跳外，服务端按需推送 `message`（新消息，双方）与 `friend_event`（申请/接受/拒绝/解除，相关方）。

- [ ] **Step 5: 更新 docs/api.md**

- REST 表追加六行：`GET /api/users/search?q=`、`GET /api/friends`、`GET /api/friends/requests`、`POST /api/friends/requests`、`POST /api/friends/requests/{from_sub}/accept|reject`、`DELETE /api/friends/{sub}`、`POST|GET /api/conversations/{sub}/messages`（鉴权/CSRF/错误码按 spec §4）。
- WebSocket 小节追加服务端推送表：`message` 与四类 `friend_event`（目标与载荷照 spec §5）。
- 状态码表追加：`409 好友/申请冲突`、`422 参数或消息内容校验失败`。

- [ ] **Step 6: 更新 docs/security.md**

清单表追加五行：

| 要求 | 实现 | 位置 |
| --- | --- | --- |
| 搜索信息泄露防护 | 匹配昵称/邮箱但只回传 sub/nickname/name/picture；查询 ≤64、结果 ≤20 | `app/friends/service.py` |
| 好友申请生命周期鉴权 | 仅被申请人可 accept/reject；仅关系一方可解除；重复/自加 409/400 | `app/friends/service.py` |
| 发消息关系校验 | 双方必须 accepted 好友；自聊 400、非好友 403 | `app/messages/service.py` |
| 历史访问边界 | 会话键 `(participant_lo, participant_hi)` 天然限定参与者 | `app/messages/service.py` |
| 消息长度与 XSS | 内容 1–2000 strip 校验；前端 `textContent`/escapeHtml 渲染不拼 HTML | `app/api/messages.py`、`static/app.js` |

- [ ] **Step 7: 真机冒烟（验收标准 §10）**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/python -m uvicorn app.main:app --reload
```

两个浏览器会话（普通/隐身）各登录一个 Li&Pass 测试账号：搜索 → 申请 → 实时事件 → 接受 → 互发消息实时可见 → 刷新后历史仍在 → 一方删除 → 双方不能再发但历史可见 → 重新申请恢复。`curl -fsS http://localhost:8000/healthz` 应返回 `{"status":"ok"}`。

- [ ] **Step 8: 提交**

```bash
git add CHANGELOG.md README.md docs/architecture.md docs/api.md docs/security.md
git commit -m "docs: 好友与单聊功能文档同步"
```

## 收尾：合并 main

- [ ] 在 `codex/friends-dm` 上 `git log --oneline` 核对 8 个 Task 提交齐全、无夹带。
- [ ] `git checkout main && git merge --no-ff codex/friends-dm -m "merge: 好友与单聊（codex/friends-dm）"`（保留 merge 记录，见 AGENTS.md §八）。
- [ ] `git worktree remove .worktrees/friends-dm` 并推送（如需远端）。
