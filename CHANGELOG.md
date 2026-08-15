# Changelog

## 未发布（开发中）

### 功能

- UI 首次设计实例化：品牌令牌（信使蓝 `#2563EB`）、明暗双主题 + 首帧防闪烁、几何 Logo/favicon、Canvas 环境呼吸层、AuthShell/AppShell 外壳与无障碍（focus-visible / aria-live / 44px 热区 / reduced-motion）
- Redis 接入（`LICHAT_REDIS_URL`）：jti 防重放改为 `SET NX EX` 原子判重，回程登出经 `lichat:logout` 频道跨副本广播断开 WS；未配置时保持进程内行为，配置后启动 PING 失败即拒绝启动

### 文档

- 新增 design-system/chat/BRAND.md、MASTER.md 与 preview 视觉基线
- 新增 docs/superpowers UI 重构设计规格与实施计划
- 补齐 .env.example 全部 LICHAT_* 配置项并同步部署指南环境变量表

### 运维工具

- 容器化部署：Dockerfile（python:3.12-slim + uv、非 root、构建期导入冒烟）与 docker-compose.yaml（单服务、命名卷持久化 SQLite、healthcheck、127.0.0.1 端口绑定）
- compose 新增编排内 redis（7-alpine、AOF、maxmemory 192mb、健康检查、口令可覆盖），chat 默认连接，支持外部 Redis 覆盖

## v0.1.0 — 2026-08-15

首个里程碑：Li&Pass OIDC 单点登录，按五个版本本地迭代交付，55 个测试、ruff、mypy 全绿。

- v1：项目骨架、配置、日志、数据库、发现文档客户端（含本地模拟 IdP）
- v2：授权码 + PKCE 登录闭环、id_token 校验、用户落库
- v3：本地会话（HttpOnly Cookie、滑动/绝对过期）、受保护路由、CSRF
- v4：RP 登出、回程登出（jti 防重放）、WebSocket 认证桥接
- v5：同源前端、真实发现文档校验、SQLite 目录自动创建、文档补全

已知事项：真实登录待 Li&Pass 门户注册 client_id/client_secret 后联调；上线前清单见 `docs/deployment.md`。
