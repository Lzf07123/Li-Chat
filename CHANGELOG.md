# Changelog

## 未发布（开发中）

### 功能

- UI 首次设计实例化：品牌令牌（信使蓝 `#2563EB`）、明暗双主题 + 首帧防闪烁、几何 Logo/favicon、Canvas 环境呼吸层、AuthShell/AppShell 外壳与无障碍（focus-visible / aria-live / 44px 热区 / reduced-motion）
- Redis 接入（`LICHAT_REDIS_URL`）：jti 防重放改为 `SET NX EX` 原子判重，回程登出经 `lichat:logout` 频道跨副本广播断开 WS；未配置时保持进程内行为，配置后启动 PING 失败即拒绝启动
- 好友与单聊（里程碑二）：昵称/邮箱关键词搜索（不回传邮箱）、申请-同意制好友关系（accept/reject/撤回/解除）、单向解除关系且历史保留、纯文本一对一实时聊天（REST 落库 + WS 双向推送）、历史消息倒序游标分页
- 好友推荐：侧栏随机推荐（排除自己/好友/待处理申请）、「添加」直达申请、刷新按钮重新随机

### 文档

- 新增 design-system/chat/BRAND.md、MASTER.md 与 preview 视觉基线
- 新增 docs/superpowers UI 重构设计规格与实施计划
- 补齐 .env.example 全部配置项：LICHAT_*、compose 插值变量与镜像加速源（`BASE_IMAGE_REGISTRY` 与 `IMAGE_REGISTRY` 拆分，避免加速前缀污染应用镜像名）
- 新增 OIDC 对接文档：门户接口契约与实现逐项对照、应用注册地址、§2.4 验收清单、上线注意事项与联调步骤

### 运维工具

- 容器化部署：Dockerfile（python:3.12-slim + uv、非 root、构建期导入冒烟）与 docker-compose.yaml（单服务、命名卷持久化 SQLite、healthcheck、127.0.0.1 端口绑定）
- compose 新增编排内 redis（7-alpine、AOF、maxmemory 192mb、健康检查、口令可覆盖），chat 默认连接，支持外部 Redis 覆盖

### 行为变更

- OIDC 授权 scope 默认加入 `email`：登录时向 Li&Pass 请求邮箱并同步到本地资料，支撑「按邮箱搜索好友」；未验证邮箱不阻塞登录（仅存储 `email_verified` 标记），授权同意页可能多一项邮箱授权

### 安全加固

- 授权单飞：同一浏览器重复发起登录时复用未完成的 auth state（`lichat_auth` HttpOnly Cookie），授权完成后即删除状态并清 Cookie——其他仍在等待的授权确认页随之作废，不再并行放行出多个会话
- 会话守护加强：RP 登出即断开该用户全部 WebSocket（配置 Redis 时跨副本广播），登出标签页不再继续收到实时消息；WS 心跳每次重新校验会话，会话被删除/过期立即以 4401 关闭

### 缺陷修复

- OIDC 传输端点升级：经 https 拉取的发现文档，其 authorization/token/userinfo/jwks/end-session 端点统一升级为 https（issuer 保留原文校验）。修复真实登录首次回调 502「idp response missing tokens」——发现文档声明 http 端点，80 端口 301 不被 httpx 的带体 POST 跟随，导致令牌响应被当成空对象
- 登出回跳页支持 POST：门户完成 SSO 登出后以 `application/x-www-form-urlencoded` 回传 `state`，原仅 GET 的路由返回 405；现同时接受 GET（query）与 POST（form，缺省回退 query），验签后 302 首页
- 登出回跳页解析放宽：POST 依次支持 query / 表单 / JSON / 原始 urlencoded body；校验失败记录 `source/content_type/字段名` 结构化日志（不落令牌值），便于定位门户实际回传格式
- 登出回跳页兼容 `logout_token`：门户实际把回程登出令牌 POST 到回跳地址（form 字段 `logout_token`）；现与 `/oidc/backchannel-logout` 共用校验与下线逻辑，令牌有效即清会话并返回 2xx，修复生产 400
- 登出回跳落回登录界面：`logout_token` 处理成功后返回 200 HTML 跳转页（meta refresh 到 `/`），浏览器自动回登录界面；门户服务器仍收到 2xx，不会继续重试
- 登出回落不再误触授权确认：前端 401 与 WS 4401 一律回到登录卡片页（不再直接跳 `/oidc/login` 触发门户授权）；落地页增加 JS 跳转兜底，避免 meta refresh 偶发不生效
- 撤销授权后会话未下线：门户 `sid` 轮换导致按 `(sub, sid)` 删除命中 0 条、会话留存；现 `sid` 缺失或未命中时回退删除该用户全部会话并断开 WS，保证撤销授权立即生效（记录诊断日志）
- 登出后浏览器后退恢复旧页面：前端监听 `pageshow`（persisted）重新校验会话并重置界面，杜绝从往返缓存恢复出仍可交互的旧页面；`/api/*` 响应统一加 `Cache-Control: no-store`
- 静态资源强制回源校验：首页与 `app.js/style.css/brand.js/theme.js/ambient.js/favicon.svg` 响应加 `Cache-Control: no-cache`（配合 ETag），杜绝网关/CDN 缓存旧前端导致登出后仍自动跳转授权确认

## v0.1.0 — 2026-08-15

首个里程碑：Li&Pass OIDC 单点登录，按五个版本本地迭代交付，55 个测试、ruff、mypy 全绿。

- v1：项目骨架、配置、日志、数据库、发现文档客户端（含本地模拟 IdP）
- v2：授权码 + PKCE 登录闭环、id_token 校验、用户落库
- v3：本地会话（HttpOnly Cookie、滑动/绝对过期）、受保护路由、CSRF
- v4：RP 登出、回程登出（jti 防重放）、WebSocket 认证桥接
- v5：同源前端、真实发现文档校验、SQLite 目录自动创建、文档补全

已知事项：真实登录待 Li&Pass 门户注册 client_id/client_secret 后联调；上线前清单见 `docs/deployment.md`。
