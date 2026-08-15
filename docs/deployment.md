# 部署指南

## 本地开发

```bash
uv sync --dev
cp .env.example .env
uv run uvicorn app.main:app --reload
```

浏览器打开 `http://localhost:8000/`。测试套件内置模拟 IdP（`tests/fixtures/mock_idp.py`），本地开发无需真实凭证；要真实登录需先在 Li&Pass「授权网站管理」注册应用。

## 容器部署（Docker Compose）

```bash
cp .env.example .env   # 按需覆盖 LICHAT_* 与 LICHAT_PORT
docker compose up -d --build
docker compose ps      # 等待 status 为 healthy
curl -fsS http://127.0.0.1:8000/healthz
docker compose logs -f chat
docker compose down    # 停止并移除容器；SQLite 数据保留在命名卷 lichat-data
```

- 端口只绑定 `127.0.0.1`，生产由 Nginx/Caddy 反代统一终止 TLS；镜像不含秘密，`.env` 被 `.dockerignore` 排除。
- **必须单 worker**：单副本内 WS 连接表仍是进程内实现；多副本需共享数据库（PostgreSQL）并配置 Redis（见下）。
- 本地 http 冒烟保持 `LICHAT_ENV=dev`；生产设 `LICHAT_ENV=prod` + ≥32 字符 `LICHAT_SESSION_SECRET`，且必须走 https（否则 Secure Cookie 不生效）。
- 构建源可在 `.env` 覆盖 `IMAGE_REGISTRY` / `PYPI_INDEX_URL` / `APT_MIRROR`（默认中科大镜像）。

### Redis（jti 防重放与跨副本登出）

compose 默认随 `chat` 启动一个编排内 redis（7-alpine、AOF、192mb、`volatile-ttl` 淘汰、默认口令 `lichat-dev-redis`，可用 `REDIS_PASSWORD` 覆盖）。`chat` 默认 `LICHAT_REDIS_URL` 指向它；三种用法：

| 模式 | 做法 |
| --- | --- |
| 编排内 redis | `docker compose up -d --build`（默认） |
| 外部 redis | 在 `.env` 设 `LICHAT_REDIS_URL=redis://:密码@主机:6379/0`，再 `docker compose up chat`（跳过本地 redis） |
| 不用 redis（单进程） | 在 `.env` 设 `LICHAT_REDIS_URL=`（空），`docker compose up chat` |

配置了 `LICHAT_REDIS_URL` 后启动会先 PING，不可达即拒绝启动（防重放能力不允许静默降级）。未配置时回退进程内实现，行为与单进程部署一致。

## 环境变量（前缀 `LICHAT_`）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LICHAT_ENV` | `dev` | `prod` 时启用 Secure Cookie 并校验密钥强度 |
| `LICHAT_DATABASE_URL` | `sqlite+aiosqlite:///./data/lichat.db` | 生产建议 PostgreSQL |
| `LICHAT_REDIS_URL` | 空（进程内实现） | 如 `redis://:pass@redis:6379/0`；配置后 jti 防重放与跨副本登出广播走 Redis |
| `LICHAT_OIDC_ISSUER` | `https://account.lizf.cn` | 发现文档地址由它推导，也可用 `LICHAT_OIDC_DISCOVERY_URL` 覆盖 |
| `LICHAT_OIDC_DISCOVERY_URL` | 空（由 issuer 推导） | 显式发现文档地址，默认 `<issuer>/.well-known/openid-configuration` |
| `LICHAT_OIDC_CLIENT_ID` | `li-chat-local` | 门户注册的 client_id |
| `LICHAT_OIDC_CLIENT_SECRET` | 空 | 机密客户端密钥 |
| `LICHAT_OIDC_REDIRECT_URI` | `http://localhost:8000/oidc/callback` | 必须精确命中门户白名单 |
| `LICHAT_OIDC_POST_LOGOUT_REDIRECT_URI` | `http://localhost:8000/` | 登出回跳白名单 |
| `LICHAT_OIDC_SCOPE` | `openid profile` | 首版不含 email，避免未验证邮箱用户被挡 |
| `LICHAT_SESSION_SECRET` | 开发占位值 | 生产必须 ≥32 字符，用于登出 state 签名 |
| `LICHAT_SESSION_SLIDING_TTL` | `7200` | 会话滑动过期秒数（2 小时） |
| `LICHAT_SESSION_ABSOLUTE_TTL` | `604800` | 会话绝对过期秒数（7 天） |
| `LICHAT_SESSION_COOKIE_NAME` | `lichat_session` | 会话 Cookie 名 |
| `LICHAT_LOGOUT_TOKEN_MAX_SKEW` | `120` | 回程登出令牌允许时钟偏差（秒）；jti 缓存保留 = 该值 + 60 |
| `LICHAT_DISCOVERY_CACHE_TTL` | `300` | 发现文档缓存时长（秒） |

compose 插值变量（应用忽略）：`LICHAT_PORT`（宿主机端口）、`REDIS_PASSWORD` / `REDIS_APPENDONLY` / `REDIS_MAXMEMORY`（编排内 redis）、`TZ`、`IMAGE_REGISTRY` / `PYPI_INDEX_URL` / `APT_MIRROR`（镜像源）。完整模板见 `.env.example`。

## 生产部署

1. 反向代理（Nginx/Caddy）统一终止 TLS；应用只需监听回环地址。
2. `LICHAT_ENV=prod` 并设置强 `LICHAT_SESSION_SECRET`。
3. 门户应用配置中填写生产回调地址、登出回跳白名单、**回程登出地址**（必须 https、非回环/私网）。
4. 数据库换 PostgreSQL，接入 Alembic 管理迁移。
5. 多副本时把 jti 防重放与会话状态迁到 Redis（当前为进程内实现）。
6. 在网关或应用层给登录/回程接口加限流。

## Issuer 注意事项

发现文档声明的 `issuer` 为 `http://account.lizf.cn`（http 字面值），但传输层实际走 https。本实现传输统一 https、令牌 `iss` 严格按发现文档原文校验；建议推动 Li&Pass 侧将 issuer 改为 https，修改后无需改代码（发现文档启动时拉取并按 TTL 缓存）。
