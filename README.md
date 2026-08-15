# Li&Chat

基于 OIDC SSO（Li&Pass）的小圈子即时通讯。当前里程碑：统一单点登录——授权码 + PKCE、本地会话、三路径登出、WebSocket 认证桥接。

## 功能

- 通过 Li&Pass 一键登录，本地不存密码，用户资料（昵称/头像）自动同步
- HttpOnly 会话 Cookie，滑动 2 小时 / 绝对 7 天
- RP 发起登出与回程登出（门户登出即时踢下线并断开实时连接）
- 同源前端：登录、资料展示、在线状态、心跳保活、退出

## 快速开始

```bash
uv sync --dev
cp .env.example .env   # 填入 Li&Pass 注册的 client_id / client_secret
uv run uvicorn app.main:app --reload
```

浏览器打开 `http://localhost:8000/`。测试套件内置模拟 IdP，无外网依赖。

容器方式：

```bash
docker compose up -d --build
```

详见 [部署指南](docs/deployment.md)。

## 质量门禁

```bash
uv run pytest -q      # 62 个测试
uv run ruff check .
uv run mypy app
```

## 项目结构

```text
app/
├── main.py        # 应用装配、生命周期、/ws、/healthz、静态挂载
├── config.py      # LICHAT_* 环境变量
├── models.py      # users / auth_states / sessions
├── auth/          # 本地会话与鉴权依赖
├── oidc/          # 依赖方实现（发现、PKCE、令牌校验、用户同步）
├── sso/           # /oidc/* 路由、登出签名、jti 防重放
├── ws/            # WebSocket 连接管理
└── api/           # /api/me
static/            # 同源前端（index.html + app/brand/theme/ambient.js + style.css 令牌）
tests/             # 62 个测试 + 本地模拟 IdP
design-system/     # 品牌设计（chat/ 项目方案 + template/ Li-Design 子模块）
Dockerfile         # 容器镜像（python:3.12-slim + uv，非 root 运行）
docker-compose.yaml # 容器编排（单服务 + SQLite 命名卷）
docs/              # 架构、接口、部署、安全文档
```

## 文档索引

- [架构说明](docs/architecture.md)
- [接口文档](docs/api.md)
- [部署指南](docs/deployment.md)
- [安全设计清单](docs/security.md)
- [品牌设计报告](design-system/chat/BRAND.md)
- [设计系统速览](design-system/chat/MASTER.md)
- [SSO 设计规格](docs/superpowers/specs/2026-08-15-li-chat-sso-design.md)
- [UI 重构设计规格](docs/superpowers/specs/2026-08-16-li-chat-ui-rebrand-design.md)
- [实施计划](docs/superpowers/plans/2026-08-15-li-chat-sso.md)
- [UI 重构实施计划](docs/superpowers/plans/2026-08-16-li-chat-ui-rebrand.md)
- [变更记录](CHANGELOG.md)

## 路线图

- [x] 里程碑一：Li&Pass 统一单点登录
- [ ] 里程碑二：好友关系与一对一实时聊天
- [ ] 里程碑三：群聊、未读/已读、离线推送
- [ ] 里程碑四：音视频（WebRTC）与更多扩展
