# 部署指南

## 本地开发

```bash
uv sync --dev
cp .env.example .env
uv run uvicorn app.main:app --reload
```

浏览器打开 `http://localhost:8000/`。测试套件内置模拟 IdP（`tests/fixtures/mock_idp.py`），本地开发无需真实凭证；要真实登录需先在 Li&Pass「授权网站管理」注册应用。

## 环境变量（前缀 `LICHAT_`）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LICHAT_ENV` | `dev` | `prod` 时启用 Secure Cookie 并校验密钥强度 |
| `LICHAT_DATABASE_URL` | `sqlite+aiosqlite:///./data/lichat.db` | 生产建议 PostgreSQL |
| `LICHAT_OIDC_ISSUER` | `https://account.lizf.cn` | 发现文档地址由它推导，也可用 `OIDC_DISCOVERY_URL` 覆盖 |
| `LICHAT_OIDC_CLIENT_ID` | `li-chat-local` | 门户注册的 client_id |
| `LICHAT_OIDC_CLIENT_SECRET` | 空 | 机密客户端密钥 |
| `LICHAT_OIDC_REDIRECT_URI` | `http://localhost:8000/oidc/callback` | 必须精确命中门户白名单 |
| `LICHAT_OIDC_POST_LOGOUT_REDIRECT_URI` | `http://localhost:8000/` | 登出回跳白名单 |
| `LICHAT_OIDC_SCOPE` | `openid profile` | 首版不含 email，避免未验证邮箱用户被挡 |
| `LICHAT_SESSION_SECRET` | 开发占位值 | 生产必须 ≥32 字符，用于登出 state 签名 |

## 生产部署

1. 反向代理（Nginx/Caddy）统一终止 TLS；应用只需监听回环地址。
2. `LICHAT_ENV=prod` 并设置强 `LICHAT_SESSION_SECRET`。
3. 门户应用配置中填写生产回调地址、登出回跳白名单、**回程登出地址**（必须 https、非回环/私网）。
4. 数据库换 PostgreSQL，接入 Alembic 管理迁移。
5. 多副本时把 jti 防重放与会话状态迁到 Redis（当前为进程内实现）。
6. 在网关或应用层给登录/回程接口加限流。

## Issuer 注意事项

发现文档声明的 `issuer` 为 `http://account.lizf.cn`（http 字面值），但传输层实际走 https。本实现传输统一 https、令牌 `iss` 严格按发现文档原文校验；建议推动 Li&Pass 侧将 issuer 改为 https，修改后无需改代码（发现文档启动时拉取并按 TTL 缓存）。
