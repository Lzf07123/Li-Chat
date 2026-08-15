# 安全设计清单

| 要求 | 实现 | 位置 |
| --- | --- | --- |
| 授权码 + PKCE S256 | verifier 用 `secrets.token_urlsafe(48)`，challenge 为 SHA256 的 base64url | `app/oidc/pkce.py` |
| state/nonce 校验且单次使用 | 服务端存储，取出即删除，10 分钟过期 | `app/oidc/state.py` |
| redirect_uri 精确匹配 | 只从配置读取，不拼接、不做前缀匹配 | `app/config.py` |
| 开放重定向防护 | `redirect_after` 仅允许站内相对路径 | `app/sso/routes.py:_safe_redirect_after` |
| id_token 校验 | iss、aud=client_id、nonce、RS256、iat/exp、按 kid 从 JWKS 选钥，密钥轮换时自动刷新 | `app/oidc/tokens.py` |
| access_token 用途限定 | 只用于调用 userinfo，不在本地校验 aud | `app/oidc/provider.py` |
| 本地会话 | HttpOnly + SameSite=Lax（生产 Secure）、滑动 2h/绝对 7d、绑定门户 sid | `app/auth/session.py` |
| CSRF | 双提交令牌，支持请求头与表单字段，`secrets.compare_digest` 比对 | `app/auth/deps.py` |
| RP 登出 state | HMAC-SHA256 签名，回跳验签 | `app/sso/signing.py` |
| 回程登出 | 验 iss/aud/120 秒新鲜窗口/jti 防重放/events，命中清会话并断 WS；`sid` 缺失或未命中时回退删除该用户全部会话（防门户 sid 轮换导致撤销授权不生效） | `app/sso/routes.py`、`app/sso/replay.py`、`app/auth/session.py` |
| 授权单飞 | 同一浏览器复用未完成 auth state（HttpOnly Cookie `lichat_auth` 记 state），完成后删除状态并清 Cookie，其余授权确认页随之作废，防止多确认页并行放行 | `app/sso/routes.py` |
| jti 防重放（Redis） | 配置 `LICHAT_REDIS_URL` 后改用 `SET NX EX` 原子判重，多副本共享 | `app/sso/replay.py`、`app/redis.py` |
| 跨副本登出广播 | 回程登出后经 `lichat:logout` 频道广播，各副本断开该用户 WS（4401） | `app/redis.py`、`app/main.py` |
| 账号封禁 | `account_blocked` 与 403 映射为友好提示，不泄露细节 | `app/sso/routes.py` |
| 生产密钥强度 | prod 环境会话密钥不足 32 字符直接拒绝启动 | `app/config.py` |
| 日志 | 结构化日志，仅记录错误码与 id，不落令牌 | `app/logging.py` |
| 搜索信息泄露防护 | 匹配昵称/邮箱但只回传 sub/nickname/name/picture；查询 ≤64、结果 ≤20 | `app/friends/service.py` |
| 好友申请生命周期鉴权 | 仅被申请人可 accept/reject；仅关系一方可解除；重复/自加 409/400 | `app/friends/service.py` |
| 发消息关系校验 | 双方必须 accepted 好友；自聊 400、非好友 403 | `app/messages/service.py` |
| 历史访问边界 | 会话键 `(participant_lo, participant_hi)` 天然限定参与者 | `app/messages/service.py` |
| 消息长度与 XSS | 内容 1–2000 strip 校验；前端 `textContent`/escapeHtml 渲染不拼 HTML | `app/api/messages.py`、`static/app.js` |

## 遗留风险（上线前处理）

- 会话已存数据库；jti 防重放与跨副本 WS 断开在配置 `LICHAT_REDIS_URL` 后由 Redis 承担。**多副本上线仍依赖共享数据库**（当前 SQLite 是本地卷，只能单副本；切 PostgreSQL + Alembic 后才能多副本）。
- Redis 未配置时进程内缓存与广播退化（仅单进程）；配置后启动 PING 失败即拒绝启动，避免静默降级。
- 登录接口暂无频率限制，需在网关或应用层加限流。
- 数据库迁移尚未引入 Alembic。
- 发现文档声明的 http 端点已在本端升级为 https 传输（2026-08-16 起，issuer 字面值仍按原文校验）；彻底收敛仍需 IdP 侧把 issuer 改为 https。注意 http→https 的 301 不会被 httpx 的带体 POST 跟随，端点必须用 https 字面值调用。
