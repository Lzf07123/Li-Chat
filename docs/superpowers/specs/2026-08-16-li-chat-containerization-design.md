# Li&Chat 容器化部署设计规格

- 状态：草稿 ｜ 日期：2026-08-16 ｜ 品牌：Li&Chat

## 1. 目标与范围

为 Li&Chat 提供容器化运行与编排方案：单服务镜像 + Docker Compose 管理，沿用 Li&Pass 的家族惯例（非 root 运行、构建期冒烟、healthcheck、127.0.0.1 端口绑定、国内镜像源可切换）。

**范围内**：`Dockerfile`、`.dockerignore`、`docker-compose.yaml`、部署文档与变更记录。

**不在范围**：PostgreSQL/Redis 编排（依赖 Alembic 迁移与进程内状态外置，属上线前事项）；Kubernetes/云容器服务清单（需要部署环境与凭据后再做）；镜像推送与 CI 流水线。

## 2. 方案

### 2.1 镜像

- 基础镜像 `python:3.12-slim`（可配 `IMAGE_REGISTRY` 前缀），装 tzdata（Asia/Shanghai）与 uv，按 `uv.lock` 用 `uv sync --frozen --no-dev` 装运行时依赖。
- 非 root 用户 `appuser`（uid 10001）运行；`/app/data` 预创建并归属该用户（SQLite 数据库路径）。
- 构建期冒烟：镜像内 `python -c "import app.main"`，把「遗漏 COPY」前移到构建阶段暴露。
- 运行命令：`uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers 1`。
- `.dockerignore` 排除 `.venv`、`.git`、缓存、`data/`、`docs/`、`design-system/`、`tests/` 与 `.env`（秘密绝不进镜像）。

### 2.2 编排

- 单服务 `chat`，命名卷 `lichat-data` 挂到 `/app/data` 持久化 SQLite；`restart: unless-stopped`、`init: true`、`no-new-privileges`。
- 环境变量显式映射 `LICHAT_*`（compose 自动读宿主机 `.env` 插值），默认 `LICHAT_ENV=dev`、数据库 `/app/data/lichat.db`。
- 端口只绑 `127.0.0.1:${LICHAT_PORT:-8000}`，生产 TLS 由外部反向代理终止。
- healthcheck 用标准库 `urllib` 请求 `/healthz`（镜像不额外装 curl）。

### 2.3 硬性约束

- **必须单 worker**：jti 防重放、会话状态与 WS 连接表均为进程内实现，多 worker/多副本会破坏回程登出与实时推送；外置 Redis 前禁止扩副本（见 docs/security.md 遗留风险）。
- 本地 http 冒烟用 `LICHAT_ENV=dev`；生产必须 `LICHAT_ENV=prod` + ≥32 字符 `LICHAT_SESSION_SECRET` + https（Secure Cookie 在 http 下不生效）。

## 3. 验收标准

- `docker compose config -q` 通过；`docker compose up -d --build` 后 `/healthz`、`/`、`/style.css`、`/app.js` 均 200。
- `docker compose ps` 显示 healthy；`docker compose down` 干净退出。
- 既有测试套件（62 个）与 ruff/mypy 不受影响。
