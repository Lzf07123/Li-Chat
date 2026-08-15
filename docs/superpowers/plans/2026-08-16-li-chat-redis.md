# Li&Chat Redis 接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Li&Chat 可连编排内/外部 Redis：jti 防重放原子化入 Redis，回程登出跨副本广播断开 WS。

**Architecture:** app/redis.py 提供客户端构建与登出广播；ReplayCache 拆为内存/Redis 双实现，统一异步 check_and_add；lifespan 负责 PING、订阅任务与清理。

**Tech Stack:** redis-py（async，运行时）、fakeredis（dev 测试）；其余不变。

## Global Constraints

- Python 3.12；测试零外网（fakeredis 替代真实 Redis）；ruff/mypy 全绿
- LICHAT_REDIS_URL 空值保持进程内行为；配置后启动 PING 失败即拒绝启动
- 键前缀 lichat:replay:；频道 lichat:logout；TTL = logout_token_max_skew + 60
- 广播仅回程登出；RP 登出行为不变
- 分支 codex/redis；每个 Task 独立提交

---

## Task 1: 依赖、Settings 与 Redis 客户端

**Files:**

- Modify: pyproject.toml、uv.lock（uv add）
- Modify: app/config.py
- Create: app/redis.py
- Test: tests/test_config.py、tests/test_redis.py

**Interfaces:**

- Consumes: 无
- Produces: Settings.redis_url: str | None；build_redis(url) -> Redis | None；LOGOUT_CHANNEL = "lichat:logout"

- [ ] **Step 1: 写失败测试**

tests/test_config.py 追加：

```python
def test_redis_url_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LICHAT_REDIS_URL", "redis://redis:6379/0")
    settings = Settings(_env_file=None)
    assert settings.redis_url == "redis://redis:6379/0"


def test_redis_url_defaults_to_none() -> None:
    settings = Settings(_env_file=None, session_secret="x" * 32)
    assert settings.redis_url is None
```

tests/test_redis.py：

```python
from app.redis import LOGOUT_CHANNEL, build_redis


def test_build_redis_none_when_unconfigured() -> None:
    assert build_redis(None) is None


def test_logout_channel_value() -> None:
    assert LOGOUT_CHANNEL == "lichat:logout"
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 最小实现**：uv add 'redis>=5,<7'、uv add --dev 'fakeredis>=2.29'；Settings 加 redis_url；新建 app/redis.py（build_redis + LOGOUT_CHANNEL）
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** feat(redis): 配置与客户端构建

## Task 2: 防重放缓存双实现

**Files:**

- Modify: app/sso/replay.py
- Modify: app/main.py（选型接线）
- Modify: app/sso/routes.py（异步 check_and_add）
- Test: tests/test_replay.py

**Interfaces:**

- Consumes: build_redis（Task 1）
- Produces: MemoryReplayCache.check_and_add(jti) -> bool、RedisReplayCache(redis, ttl, prefix) 同签名；app.state.replay_cache 恒有该接口

- [ ] **Step 1: 写失败测试** tests/test_replay.py（内存判重/过期、Redis 原子判重 + TTL、前缀隔离）
- [ ] **Step 2: 运行确认失败**（check_and_add 不存在）
- [ ] **Step 3: 最小实现**：replay.py 重写为两实现；main.py 按 app.state.redis 选型；routes.py 改 await cache.check_and_add(jti)
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** feat(redis): jti 防重放内存/Redis 双实现

## Task 3: 登出广播与订阅

**Files:**

- Modify: app/redis.py（publish_logout、logout_subscriber）
- Modify: app/main.py（lifespan：PING、订阅任务、清理；redis 注入参数）
- Modify: app/sso/routes.py（回程登出后发布）
- Test: tests/test_backchannel_redis.py

**Interfaces:**

- Consumes: Task 2 产物
- Produces: publish_logout(redis, sub)、logout_subscriber(redis, manager)；create_app(..., redis=...)

- [ ] **Step 1: 写失败测试**：共享 FakeRedis 的两个 app，app B 注册 FakeWS，app A 收到回程登出 → B 的 WS 以 4401 关闭、重复 jti 被忽略（订阅任务在测试中显式启动）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 最小实现**：publish_logout 用 redis.publish；logout_subscriber 监听频道并 disconnect_sub；lifespan 接线与清理
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** feat(redis): 回程登出跨副本广播

## Task 4: 编排内 Redis 与文档

**Files:**

- Modify: docker-compose.yaml（redis 服务 + chat 环境变量）
- Modify: .env.example
- Modify: docs/deployment.md、docs/security.md、docs/architecture.md、CHANGELOG.md、README.md、AGENTS.md

- [ ] **Step 1:** compose 加 redis 服务与 lichat-redis-data 卷；chat 加 LICHAT_REDIS_URL 默认指向内部 redis
- [ ] **Step 2:** 文档同步（部署 Redis 章节、遗留风险修正、架构地图、变更记录）
- [ ] **Step 3: 提交** feat(ops): 编排内 redis 与文档同步

## Task 5: 冒烟与合并

- [ ] 全量门禁：pytest/ruff/mypy
- [ ] docker compose up -d --build：chat 与 redis 均 healthy，/healthz 200；docker compose exec redis redis-cli -a ... ping 返回 PONG
- [ ] 外部不可达 URL 冒烟：临时 LICHAT_REDIS_URL=redis://127.0.0.1:6399/0 启动应拒绝启动
- [ ] 合并 main 并删分支
