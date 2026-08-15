# Li&Chat

基于 OIDC SSO（Li&Pass）的小圈子即时通讯。当前里程碑：统一单点登录（授权码 + PKCE、本地会话、三路径登出、WebSocket 认证桥接）。

## 本地运行

```bash
uv sync --dev
cp .env.example .env   # 填入 Li&Pass 注册的 client_id / client_secret
uv run uvicorn app.main:app --reload
```

浏览器打开 `http://localhost:8000/`，点击"使用 Li&Pass 登录"。

## 质量门禁

```bash
uv run pytest -q      # 54 个测试，本地模拟 IdP，无外网依赖
uv run ruff check .
uv run mypy app
```

## 安全设计要点

- 授权码 + PKCE S256，state/nonce 服务端存储且单次使用
- id_token：iss/aud(=client_id)/nonce/RS256/JWKS kid 选钥逐项校验
- 传输层 https，`iss` 按发现文档原文（`http://account.lizf.cn`）比对
- 本地会话 HttpOnly + SameSite=Lax（生产加 Secure），滑动 2h / 绝对 7d
- CSRF 双提交令牌；登出 state 带 HMAC 签名
- 回程登出：iss/aud/120s 时间窗/jti 防重放/events 校验，命中即清会话并断开 WS
- 生产环境要求 `LICHAT_SESSION_SECRET` 至少 32 字符

## 上线前待办

- 引入 Alembic 管理数据库迁移
- 多副本部署时：jti 防重放缓存与会话状态迁移到 Redis
- 登录/回程接口加限流（slowapi 或网关层）
- 反向代理统一终止 TLS，并配置生产回程登出地址（https）
- 与 Li&Pass 团队确认发现文档 issuer 的 http/https 不一致问题

详见 [docs/superpowers/specs/2026-08-15-li-chat-sso-design.md](docs/superpowers/specs/2026-08-15-li-chat-sso-design.md) 与 [docs/superpowers/plans/2026-08-15-li-chat-sso.md](docs/superpowers/plans/2026-08-15-li-chat-sso.md)。
