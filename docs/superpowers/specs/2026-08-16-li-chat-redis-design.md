# Li&Chat Redis 接入设计规格

- 状态：草稿 ｜ 日期：2026-08-16 ｜ 品牌：Li&Chat

## 1. 目标与范围

让 Li&Chat 可连接编排内 Redis 或外部 Redis，把两类进程内状态外置，为多副本部署打基础：

1. jti 防重放缓存：回程登出的 logout_token jti 判重。
2. 跨副本 WS 断开：某副本收到回程登出后，所有副本立即断开该用户连接。

**不在范围**：会话存储迁移（会话已在数据库）；SQLite → PostgreSQL 迁移；限流；多副本完整上线（需共享数据库后才能多副本）。

## 2. 现状

- 会话表 sessions 已在数据库，跨副本天然共享；docs/security.md「会话状态为进程内」的表述过时，本次一并修正。
- app/sso/replay.py 的 ReplayCache 是进程内 dict，seen/add 两步存在 TOCTOU。
- app/ws/manager.py 的 ConnectionManager 是进程内连接表；回程登出只断开本副本连接。

## 3. 方案

### 3.1 配置与降级

- 新增 LICHAT_REDIS_URL（Settings.redis_url: str | None，默认空）。
- 空值 = 未启用：保持现有进程内行为（单副本）；配置值 = 启用 Redis。
- 启用后启动时 PING，失败即拒绝启动（防重放是安全能力，不允许静默降级），并打结构化日志。

### 3.2 防重放缓存

- 抽象为异步单方法 check_and_add(jti) -> bool：返回 True 表示重放，原子完成「已存在判定 + 写入」。
- MemoryReplayCache：保留现逻辑（单进程）。
- RedisReplayCache：SET <key> 1 EX <ttl> NX，返回 None 即已存在（重放）。键前缀 lichat:replay:，TTL = logout_token_max_skew + 60。
- 路由改为 if await cache.check_and_add(jti): return ignored。

### 3.3 登出广播（pub/sub）

- 频道 lichat:logout，消息 {"sub": "<user_sub>"}。
- 回程登出处理本地会话与本地 WS 后发布事件；每个副本在 lifespan 启动订阅任务，收到后 ConnectionManager.disconnect_sub(sub, code=4401)。
- RP 发起登出只清当前会话、不广播（与现状一致）；广播仅回程登出。

### 3.4 接线

- create_app(settings, *, http_transport=None, redis=None)：新增可注入 redis（测试用）；默认按 redis_url 构建 redis.asyncio.Redis（decode_responses=True）。
- lifespan：PING、启动订阅任务；关闭时取消任务并 aclose。

### 3.5 编排

- compose 新增 redis 服务（7-alpine、AOF、maxmemory 192mb、volatile-ttl 淘汰、健康检查、不发布端口、默认口令 lichat-dev-redis 可覆盖）。
- chat 默认 LICHAT_REDIS_URL=redis://:<口令>@redis:6379/0；外部 Redis 在 .env 覆盖 LICHAT_REDIS_URL；纯外部模式用 docker compose up chat 跳过本地 redis。

## 4. 测试策略

- 依赖 fakeredis（dev，纯 Python，零网络）：
  - MemoryReplayCache / RedisReplayCache 判重与过期语义、前缀隔离；
  - 两个共享同一 FakeRedis 的 app：app A 收到回程登出 → app B 的 FakeWS 被 4401 关闭，且重复 jti 被忽略；
  - LICHAT_REDIS_URL 解析。
- 容器冒烟：docker compose up -d --build 后 chat 与 redis 均 healthy；外部 URL 路径用假地址验证「配置但不可达 → 拒绝启动」。

## 5. 验收标准

- 全部既有 62 个测试与新增测试通过，ruff/mypy 全绿。
- 未配置 Redis 时行为与现在完全一致；配置后 jti 判重与登出广播在 FakeRedis 上跨「副本」生效。
- compose 双服务 healthy；/healthz 200。
