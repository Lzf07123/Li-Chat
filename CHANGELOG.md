# Changelog

## 未发布（开发中）

### 功能

- 消息引用回复：`messages.reply_to_id`（自引用 FK）与同会话校验（单聊 pair / 群 group_id，
  跨会话 404）、引用预览 `reply_to`（内容 ≤100 截断、已撤回显示墓碑、不递归嵌套）；单聊与
  群发送接口加 `reply_to_id`；前端消息「回复」按钮与输入框引用条（可取消）
- 音视频呼叫信令（里程碑四起点）：WS `call` 协议 `offer/answer/ice/reject/end` 与
  `busy/invalid/unavailable/error` 应答；仅好友间、载荷 ≤16KB、ICE 限频、进程内状态机
  （idle→ringing→connected→ended）、信令不落库不记日志；前端 WebRTC 1:1 呼叫（发起/来电
  接听/拒绝/挂断）；媒体为 P2P，服务端只中转信令
- 个人资料与头像：`PATCH /api/me`（昵称 1–32 / 简介 ≤200，简介仅好友可见）、
  `POST /api/me/avatar`（引用本人上传的图片，非图片 422 / 他人附件 403）；前端资料编辑弹层
  与头像上传
- 全文搜索：`GET /api/search?kind=messages|contacts`——消息检索限定自己可见范围（单聊双方 /
  群成员）、LIKE 不区分大小写、倒序游标分页、命中片段前后截断脱敏；联系人检索复用好友搜索
  语义（附 friend_status）；前端搜索框「用户/消息」双模式、命中跳转与加载更多
- 附件与图片消息：上传端点（`LICHAT_UPLOAD_MAX_MB` 默认 10、≤20；内容嗅探白名单
  jpeg/png/gif/webp/pdf/txt，拒绝 SVG/HTML 与伪造类型；随机文件名防遍历）、`uploads`
  表、会话鉴权回源（仅上传者可下载、nosniff、图片 inline / 其他 attachment）、消息
  `content_type + attachment` 元数据（单聊 + 群）与附件归属校验；前端附件按钮与图片/文件
  消息渲染
- 群消息与群已读（里程碑三核心）：`messages` 会话抽象（`conversation_type dm|group` +
  `group_id`，SQLite 兼容迁移自动补列、旧 DM 数据不动；群消息以 `group:{id}` 哨兵占位
  recipient/participant 满足旧库约束）、`group_reads` 已读游标（只前进）、群发送/历史
  分页/标记已读（仅成员）、`GET /api/conversations` 合并群摘要（peer/group 二选一）、WS
  群消息与群已读回执广播全成员；前端群聊天区、群未读徽标、打开即已读
- 群聊管理（里程碑三）：建群（初始成员必须为创建者好友、单请求 ≤20、容量 200）、群列表/
  详情、改名（owner/admin）、邀请（owner/admin，好友闸）、移除（admin 不得移除 owner 或
  admin，owner 可移除 admin）、角色调整（owner 专属）、退出（owner 需先转让）、转让群主；
  WS `group_event` 全成员广播；前端群列表、建群弹层、群详情与成员/角色管理
- 表情回应：`reactions` 表复合主键幂等 toggle（`PUT`/`DELETE
  /api/conversations/{sub}/messages/{id}/reactions`，emoji 1–8 字符、禁空白与控制符、
  已撤回 409、非参与者 404）；历史消息附 `reactions` 聚合与 `my_reactions`；WS
  `message_reaction` 定向双方；前端回应栏 + 快捷 emoji + 点击切换
- 消息编辑与撤回：发送者 5 分钟内可 `PATCH` 编辑（回显 `edited_at`）或 `DELETE` 撤回
  （content 清空落库，历史与 WS 只回墓碑不泄露原文）；WS `message_edited`/
  `message_deleted` 定向双方；前端编辑态与撤回按钮、墓碑与「已编辑」标记
- 在线状态与正在输入：好友上线/下线 presence 广播（仅好友可见）、`users.last_seen_at`
  （连接与心跳写入）、`GET /api/friends` 附 `online`/`last_seen_at`；typing `start/stop`
  定向中继（仅好友、2 秒限频、非法/非好友静默丢弃）；前端好友在线圆点、会话头部在线
  状态与「正在输入…」提示
- 未读计数与已读回执（里程碑三起点）：会话列表摘要（最后消息 + 未读数 + 已读游标）、
  `GET /api/conversations` 与 `POST /api/conversations/{sub}/read`（游标只前进、消息必须
  属于该会话、非好友 403）、WS `read_receipt` 定向回执、发送方发送后自动推进游标；前端
  好友栏未读徽标与最后消息预览、打开会话即标记已读、消息气泡「已读」指示
- UI 首次设计实例化：品牌令牌（信使蓝 `#2563EB`）、明暗双主题 + 首帧防闪烁、几何 Logo/favicon、Canvas 环境呼吸层、AuthShell/AppShell 外壳与无障碍（focus-visible / aria-live / 44px 热区 / reduced-motion）
- Redis 接入（`LICHAT_REDIS_URL`）：jti 防重放改为 `SET NX EX` 原子判重，回程登出经 `lichat:logout` 频道跨副本广播断开 WS；未配置时保持进程内行为，配置后启动 PING 失败即拒绝启动
- 好友与单聊（里程碑二）：昵称/邮箱关键词搜索（不回传邮箱）、申请-同意制好友关系（accept/reject/撤回/解除）、单向解除关系且历史保留、纯文本一对一实时聊天（REST 落库 + WS 双向推送）、历史消息倒序游标分页
- 好友推荐：侧栏随机推荐（排除自己/好友/待处理申请）、「添加」直达申请、刷新按钮重新随机

### 文档

- 新增 design-system/chat/BRAND.md、MASTER.md 与 preview 视觉基线
- 新增 docs/superpowers UI 重构设计规格与实施计划
- 补齐 .env.example 全部配置项：LICHAT_*、compose 插值变量与镜像加速源（`BASE_IMAGE_REGISTRY` 与 `IMAGE_REGISTRY` 拆分，避免加速前缀污染应用镜像名）
- 新增 OIDC 对接文档：门户接口契约与实现逐项对照、应用注册地址、§2.4 验收清单、上线注意事项与联调步骤
- OIDC 配置口径固化：明确标准登记值（回程登出地址 `/oidc/backchannel-logout`、登出回跳白名单 `/`），`/oidc/post-logout` 的 `logout_token` 分支标注为旧门户行为兼容兜底

### 运维工具

- 容器化部署：Dockerfile（python:3.12-slim + uv、非 root、构建期导入冒烟）与 docker-compose.yaml（单服务、命名卷持久化 SQLite、healthcheck、127.0.0.1 端口绑定）
- compose 新增编排内 redis（7-alpine、AOF、maxmemory 192mb、健康检查、口令可覆盖），chat 默认连接，支持外部 Redis 覆盖

### 行为变更

- SSO 资料同步改为「昵称/头像仅空值回填」：本地编辑的个人资料不再被门户 userinfo 覆盖
  （`name`/`email` 仍随登录同步）
- SQLite 连接启用 `journal_mode=WAL` 与 `busy_timeout=5000`：缓解读写并发互锁与瞬时
  锁竞争（生产同样受益；PostgreSQL 不受影响）
- OIDC 授权 scope 默认加入 `email`：登录时向 Li&Pass 请求邮箱并同步到本地资料，支撑「按邮箱搜索好友」；未验证邮箱不阻塞登录（仅存储 `email_verified` 标记），授权同意页可能多一项邮箱授权
- RP 登出携带 `id_token_hint`：登录时把 `id_token` 存进本地会话（仅作登出提示），网站内退出登录跳门户 `end-session` 时随 `client_id` 一起携带，门户据此展示「退出所有会话 / 仅退出当前网站」确认页，而不是打回授权确认
- 移除 `/oidc/post-logout` 的兼容逻辑：该端点恢复标准形态（仅 GET 带签名 `state` 回跳，验签后 302 首页），POST/`logout_token` 一律 405；回程登出统一走 `/oidc/backchannel-logout`

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
