# Li&Chat SSO 实施计划（本地五版本迭代）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用本地模拟 IdP 完成 Li&Chat 的 OIDC SSO 接入：登录闭环、本地会话、三路径登出与 WebSocket 认证桥接，五个版本迭代，每个版本全绿并提交。

**Architecture:** FastAPI 单进程应用同源托管前端；REST 处理登录/会话，WebSocket 复用同源 Cookie 认证。OIDC 依赖方逻辑自研（httpx + pyjwt），用 FastAPI ASGI 模拟 IdP 做集成测试，无真实网络依赖。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2.0 async + aiosqlite、httpx、pyjwt[crypto]、pydantic-settings、structlog；测试 pytest + pytest-asyncio + httpx(ASGITransport)；质量 ruff + mypy。

## Global Constraints

- Python 3.12（uv 管理），依赖锁定在 `uv.lock`
- 所有测试走 ASGI 内存传输（`httpx.ASGITransport`），不监听端口、不访问外网
- issuer 字面值按发现文档原文（`http://account.lizf.cn`）校验；传输层统一 https
- `sub` 是用户主键；本地不存任何密码
- 令牌校验必须逐项覆盖：iss、aud（id_token=client_id）、nonce、RS256 验签、kid 选钥、iat/exp
- 回程登出必须校验：iss/aud、120 秒新鲜窗口、jti 防重放、events 字段
- 每个版本：`pytest` 全绿 + `ruff check` + `mypy` 无告警后 commit；违反即回炉

---

## Task V1: 项目骨架、配置、数据库、发现文档客户端

**Files:**

- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `pytest.ini`, `README.md`
- Create: `app/__init__.py`, `app/config.py`, `app/logging.py`, `app/db.py`, `app/models.py`, `app/main.py`
- Create: `app/oidc/__init__.py`, `app/oidc/discovery.py`
- Test: `tests/conftest.py`, `tests/fixtures/mock_idp.py`, `tests/test_config.py`, `tests/test_discovery.py`, `tests/test_models.py`, `tests/test_health.py`

**Interfaces:**

- Produces:
  - `Settings` (pydantic-settings)：`oidc_issuer`、`oidc_client_id`、`oidc_client_secret`、`oidc_redirect_uri`、`oidc_post_logout_redirect_uri`、`oidc_scope="openid profile"`、`session_secret`、`session_sliding_ttl=7200`、`session_absolute_ttl=604800`、`session_cookie_name="lichat_session"`、`database_url`、`logout_token_max_skew=120`、`discovery_cache_ttl=300`
  - `OIDCMetadata`（dataclass：issuer/authorization_endpoint/token_endpoint/userinfo_endpoint/jwks_uri/end_session_endpoint/scopes_supported/backchannel_logout_supported）
  - `DiscoveryStore(discovery_url, *, transport: httpx.AsyncBaseTransport | None = None, ttl: int)` → `async get() -> OIDCMetadata`，缓存带 TTL，失败抛 `DiscoveryError`
  - 模型 `User`(sub PK, nickname, name, picture, email, email_verified, created_at, updated_at)、`AuthState`(state PK, verifier, nonce, redirect_after, expires_at)、`Session`(id PK, user_sub FK, sid, acr, csrf_token, created_at, last_seen_at, expires_at, absolute_expires_at)
  - `create_app(settings: Settings | None = None) -> FastAPI`，lifespan 建表，`GET /healthz`

- [ ] **Step 1: 写失败测试**

```python
def test_discovery_returns_metadata(discovery_store):
    meta = asyncio.run(discovery_store.get())
    assert meta.issuer == "http://mock-idp.test"
    assert meta.jwks_uri.endswith("/oauth2/jwks")

def test_discovery_cached_within_ttl(discovery_store):
    first = asyncio.run(discovery_store.get())
    second = asyncio.run(discovery_store.get())
    assert first is second
```

- [ ] **Step 2: 运行确认失败** `pytest tests/test_discovery.py -v` → FAIL（模块不存在）
- [ ] **Step 3: 最小实现** 用 `httpx.AsyncClient(transport=...)` GET 发现文档 → 解析 → 缓存 `(metadata, fetched_at)`；校验必填端点，缺失抛 `DiscoveryError`
- [ ] **Step 4: 运行确认通过** → PASS
- [ ] **Step 5: commit** `git commit -m "feat(v1): 项目骨架与 OIDC 发现文档客户端"`

## Task V2: 授权码 + PKCE 登录闭环

**Files:**

- Create: `app/oidc/pkce.py`, `app/oidc/state.py`, `app/oidc/tokens.py`, `app/oidc/provider.py`, `app/oidc/user_sync.py`, `app/sso/__init__.py`, `app/sso/routes.py`
- Test: `tests/test_pkce.py`, `tests/test_state.py`, `tests/test_provider.py`, `tests/test_login.py`, `tests/test_user_sync.py`

**Interfaces:**

- Consumes: `Settings`、`OIDCMetadata`、模型
- Produces:
  - `generate_pkce_pair() -> tuple[str, str]`（verifier、S256 challenge）
  - `create_auth_state(db, *, verifier, nonce, redirect_after, ttl=600) -> str`
  - `pop_auth_state(db, state) -> AuthState | None`（单次使用）
  - `TokenVerifier(issuer, client_id, jwks_uri, *, transport=None)` → `validate_id_token(token, nonce) -> dict`、`validate_logout_token(token) -> dict`（V4 用）
  - `OIDCProvider(settings, discovery) -> build_authorize_url(state, nonce, challenge) -> str`、`exchange_code(code, verifier) -> dict`、`fetch_userinfo(access_token) -> dict`
  - `upsert_user(db, userinfo: dict) -> User`
  - 路由：`GET /oidc/login`、`GET /oidc/callback`

- [ ] **Step 1: 写失败测试** 覆盖：PKCE 向量自检；state 单次使用与过期；authorize URL 参数完整（response_type=code、scope、state、nonce、code_challenge、S256）；happy path 完整登录后 `users` 表出现 `sub="u-1001"`；回调 state 不匹配返回 400；code 重放第二次被拒；`access_denied` 映射友好错误；id_token 的 iss/aud/nonce 任一错误都拒绝
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 最小实现** state/nonce 用 `secrets.token_urlsafe`；授权码交换 POST form（`grant_type/code/redirect_uri/client_id/client_secret/code_verifier`）；`TokenVerifier` 自拉 JWKS → `PyJWKClient.from_json` → `jwt.decode(algorithms=["RS256"], audience=client_id, issuer=issuer)` → 再比对 nonce
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: commit** `git commit -m "feat(v2): 授权码+PKCE 登录闭环"`

## Task V3: 本地会话与受保护路由

**Files:**

- Create: `app/auth/__init__.py`, `app/auth/session.py`, `app/auth/deps.py`, `app/api/__init__.py`, `app/api/users.py`
- Test: `tests/test_session.py`, `tests/test_me.py`

**Interfaces:**

- Consumes: `Settings`、`Session` 模型
- Produces:
  - `create_session(db, user_sub, *, sid=None, acr=None) -> Session`（随机 id + csrf_token）
  - `get_session(db, session_id) -> Session | None`（滑动续期，超绝对上限返回 None）
  - `delete_session(db, session_id)`、`delete_sessions_for(db, sub, sid)`
  - `set_session_cookie(response, session_id)`、`clear_session_cookie(response)`
  - `get_current_user` 依赖（无 Cookie/无效/过期 → 401）；`require_csrf` 依赖（header `X-CSRF-Token` 与 session.csrf_token 比对）
  - `GET /api/me` 返回 `{sub, nickname, name, picture, csrf_token}`

- [ ] **Step 1: 写失败测试** 覆盖：滑动续期改变 `expires_at`；超绝对上限判 None；登录后 `/api/me` 返回 profile；无 Cookie 401；过期会话 401；乱造 Cookie 401
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 最小实现** Cookie 属性 `HttpOnly + SameSite=Lax + Path=/`，`Secure` 仅 prod；`get_current_user` 读 Cookie → 查库 → 返回 User
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: commit** `git commit -m "feat(v3): 本地会话与受保护路由"`

## Task V4: 登出三路径与 WebSocket 桥接

**Files:**

- Create: `app/ws/__init__.py`, `app/ws/manager.py`, `app/sso/backchannel.py`
- Modify: `app/sso/routes.py`（`POST /oidc/logout`、`GET /oidc/post-logout`、`POST /oidc/backchannel-logout`）、`app/main.py`（挂 `/ws`）
- Test: `tests/test_logout.py`, `tests/test_backchannel.py`, `tests/test_ws.py`

**Interfaces:**

- Consumes: `TokenVerifier.validate_logout_token`、会话接口、`OIDCMetadata.end_session_endpoint`
- Produces:
  - `ConnectionManager`：`connect(sub, ws)`、`disconnect(sub, ws)`、`disconnect_sub(sub)`、`send_to(sub, payload)`
  - `POST /oidc/logout`（require_csrf）：删会话 → 302 到 `end_session?client_id=...&post_logout_redirect_uri=...&state=...`（state 用 `session_secret` HMAC 签名，防篡改）
  - `GET /oidc/post-logout`：验签 state → 302 首页；失败 400
  - `POST /oidc/backchannel-logout`：form `logout_token` → 校验 iss/aud/120s 窗/jti 防重放/events → `delete_sessions_for(sub, sid)` + `disconnect_sub(sub)`；始终返回 2xx，校验失败 400
  - `GET /ws`：Cookie 会话校验失败 close(4401)；成功 `connect(sub, ws)`

- [ ] **Step 1: 写失败测试** 覆盖：登出跳转参数正确；无 CSRF 头 403；post-logout state 篡改 400；合法 logout_token 清除 `(sub,sid)` 会话并断开 WS；同 jti 重放第二次不再触发副作用；aud/iat/events 任一非法 400；WS 无会话 4401、有会话接受、回程登出后收到断开
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 最小实现** jti 缓存用进程内 dict + 过期清理（单进程部署说明写进 README）；签名用 `hmac.new(secret, state, sha256)`
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: commit** `git commit -m "feat(v4): 登出三路径与 WebSocket 认证桥接"`

## Task V5: 同源前端、真实发现文档、质量门禁

**Files:**

- Create: `static/index.html`, `static/app.js`, `static/style.css`
- Modify: `app/main.py`（StaticFiles 挂载）、`README.md`（运行说明、安全清单、生产切换项）
- Test: `tests/test_frontend.py`, `tests/fixtures/real_discovery.json`, `tests/test_real_discovery.py`

**Interfaces:**

- Consumes: 全部既有接口
- Produces: `GET /` 返回 `static/index.html`；前端含登录按钮（跳 `/oidc/login`）、`/api/me` 展示、登出按钮（带 CSRF 头 POST `/oidc/logout`）、WS 状态指示（`/ws`）

- [ ] **Step 1: 写失败测试** 覆盖：`/` 返回 200 且 text/html；静态资源 200；对真实发现文档 JSON 快照解析出全部端点（快照即 2026-08-15 实测内容）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 最小实现** 静态页 + 挂载；README 与 .env.example 补全
- [ ] **Step 4: 运行全量门禁** `pytest -q`、`ruff check .`、`mypy app` 全部通过
- [ ] **Step 5: commit** `git commit -m "feat(v5): 同源前端与质量门禁"`

## Self-Review

- 规格覆盖：设计文档第 4~9 节的每条要求均有对应任务；scope 策略与回程登出降级在 README 说明。
- 占位扫描：无 TBD/TODO；所有接口给出签名与返回类型。
- 类型一致：`TokenVerifier.validate_logout_token` 在 V2 定义、V4 使用，签名一致；`Session.csrf_token` 在 V1 建表、V3/V4 使用，字段一致。
