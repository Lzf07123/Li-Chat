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
| 会话守护 | RP 登出/回程登出/撤销授权均断开该用户 WS（Redis 时跨副本广播）；WS 心跳逐次重校验会话，失效即 4401 关闭 | `app/sso/routes.py`、`app/main.py` |
| CSRF | 双提交令牌，支持请求头与表单字段，`secrets.compare_digest` 比对 | `app/auth/deps.py` |
| RP 登出 state | HMAC-SHA256 签名，回跳验签 | `app/sso/signing.py` |
| RP 登出 hint | `id_token` 仅存本地会话表作为 `end-session` 的 `id_token_hint`（5 分钟寿命令牌），随会话删除/过期一并清除，不落前端与日志 | `app/models.py`、`app/sso/routes.py` |
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
| presence 信息泄露防护 | 上线/下线仅向好友广播；`GET /api/friends` 的 online/last_seen_at 仅对好友可见 | `app/main.py`、`app/api/friends.py` |
| typing 信令防护 | 仅好友间中继、`start|stop` 白名单、按 (发送方,目标) 2 秒限频，非法请求静默丢弃 | `app/ws/relay.py`、`app/ws/manager.py` |
| 消息编辑/撤回鉴权 | 仅发送者、5 分钟窗口、撤回后不可再编辑；撤回清空 content 落库，历史与 WS 只回墓碑不泄露原文 | `app/messages/service.py` |
| 表情回应防护 | 仅会话参与者可回应；emoji 1–8 字符、禁空白与控制符；已撤回消息 409；聚合只回 `{emoji,count}` 不泄露用户清单 | `app/messages/service.py` |
| 群聊权限矩阵 | 详情仅成员可见；改名/邀请需 owner/admin；移除规则（admin 不可移除 owner/admin）；角色调整/转让仅 owner；退出 owner 需先转让；邀请好友闸 + 容量上限 | `app/groups/service.py` |
| 群消息访问边界 | 发/读/已读仅群成员；群已读游标只前进且消息必须属于该群；退群后群摘要消失、历史不可见 | `app/messages/service.py` |
| 附件安全 | 内容嗅探白名单（jpeg/png/gif/webp/pdf/txt），拒绝 SVG/HTML 与伪造类型；大小 ≤20MB；随机文件名防遍历；回源会话鉴权（上传者或引用该附件的会话参与者）+ nosniff；附件消息归属校验 | `app/uploads/`、`app/messages/service.py` |
| 转发边界 | 源消息必须自己可见（单聊双方/群成员）且未撤回；目标好友/群成员校验；不得转发给自己 | `app/messages/service.py` |
| 提及防护 | 单聊仅可提及对方、群仅可提及成员；≤50 去重；非法提及 422 | `app/messages/service.py` |
| 收藏边界 | 只能收藏自己可见范围（单聊双方/群成员）的消息；越权 404 | `app/messages/service.py` |
| 会话设置归属 | 置顶/免打扰键必须归属本人（单聊包含自己、群为成员），越权 404 | `app/messages/service.py` |
| 群公告/头像权限 | 仅 owner/admin 可维护；头像必须为本人上传的图片；公告长度上限 | `app/groups/service.py` |
| 群消息操作边界 | 编辑/撤回仅发送者且 5 分钟内；表情仅群成员；非成员 404 | `app/messages/service.py` |
| 搜索信息泄露防护 | 消息搜索限定自己可见范围（单聊双方 / 群成员）；排除已撤回；命中片段截断；q ≤64、limit ≤50 | `app/search/service.py` |
| 资料与头像防护 | 昵称/简介长度校验；简介仅好友可见（搜索不回传）；头像必须为本人上传的图片；CSRF 保护 | `app/api/users.py`、`app/friends/service.py` |
| 备注名边界 | 备注仅本人可见、长度 ≤32（空串清除）；仅已接受好友关系可设置，非好友 404；不下发他人 | `app/friends/service.py`、`app/api/friends.py` |
| 呼叫信令防护 | 仅好友间、载荷 ≤16KB、ICE 限频、状态机校验非法迁移；信令不落库、SDP 不记日志；媒体 P2P 不经服务端 | `app/ws/calls.py` |
| 登录限流 | `/oidc/login` 与 `/oidc/callback` IP 粒度滑动窗口，超限 429 + Retry-After（进程内实现） | `app/sso/ratelimit.py`、`app/sso/routes.py` |
| 会话治理 | 仅能列出/撤销自己的会话；撤销即断对应 WS（4401）；退出其他设备保留当前会话 | `app/api/users.py`、`app/ws/manager.py` |
| 呼叫记录边界 | 仅自己作为主叫/被叫的记录可见；状态如实落账 | `app/api/users.py`、`app/ws/calls.py` |
| 消息长度与 XSS | 内容 1–2000 strip 校验；前端 `textContent`/escapeHtml 渲染不拼 HTML | `app/api/messages.py`、`static/app.js` |
| 敏感接口禁缓存 | `/api/*` 响应统一 `Cache-Control: no-store`，防浏览器/代理缓存会话数据 | `app/main.py` |

## 遗留风险（上线前处理）

- 会话已存数据库；jti 防重放与跨副本 WS 断开在配置 `LICHAT_REDIS_URL` 后由 Redis 承担。**多副本上线仍依赖共享数据库**（当前 SQLite 是本地卷，只能单副本；切 PostgreSQL + Alembic 后才能多副本）。
- Redis 未配置时进程内缓存与广播退化（仅单进程）；配置后启动 PING 失败即拒绝启动，避免静默降级。
- 登录限流为进程内实现；多副本部署需在网关或共享存储层限流（当前已按 IP 滑动窗口缓解单进程暴力尝试）。
- 数据库迁移尚未引入 Alembic。
- 发现文档声明的 http 端点已在本端升级为 https 传输（2026-08-16 起，issuer 字面值仍按原文校验）；彻底收敛仍需 IdP 侧把 issuer 改为 https。注意 http→https 的 301 不会被 httpx 的带体 POST 跟随，端点必须用 https 字面值调用。
