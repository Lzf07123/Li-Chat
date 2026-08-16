# Li&Chat 主流 IM 功能路线图（v1–v10）设计规格

日期：2026-08-16
分支：`codex/im-roadmap-v1-v10`

## 目标

在已交付的里程碑一（Li&Pass OIDC SSO）与里程碑二（好友关系 + 纯文本单聊）之上，按主流
即时通讯产品的公共能力谱系，自主迭代 10 个功能版本，补齐里程碑三（群聊、未读/已读、离线
同步方向）与里程碑四（音视频信令方向）并覆盖主流 IM 标配的消息操作能力。

**原则**（延续 AGENTS.md 硬性规则）：安全不降级；测试零外网（httpx ASGITransport + 本地
模拟 IdP）；路由薄、业务进 service；每个版本独立验收（pytest / ruff / mypy 全绿）与独立
提交；CHANGELOG 与受影响的 docs 同步更新。

## 现状盘点（2026-08-16，基线 120 测试全绿）

- 已有：会话/Cookie/CSRF、WS 认证桥接与心跳（4401 约定）、好友申请生命周期、纯文本单聊
  （REST 落库 + WS 双向推送）、单聊历史倒序游标分页。
- 缺失（本路线图覆盖）：未读/已读、在线状态/正在输入、消息编辑/撤回、表情回应、群聊、
  群消息与群已读、附件/图片消息、全文搜索、个人资料编辑/头像、音视频呼叫信令。

## 版本总览与依赖

各版本严格串行（共享 `models.py` / `main.py` / WS 协议 / docs / CHANGELOG，零文件重叠不可
并行）。每版产出：后端契约 + 测试 + 必要的前端增量 + 文档同步。

| 版本 | 主题 | 关键交付 |
| --- | --- | --- |
| v1 | 未读计数与已读回执 | 会话列表（最后消息 + 未读数）、标记已读、WS 已读回执 |
| v2 | 在线状态与正在输入 | presence 广播、last_seen、typing 中继（仅好友） |
| v3 | 消息编辑与撤回 | 编辑窗口、撤回墓碑、编辑/撤回 WS 事件 |
| v4 | 表情回应 | reactions 表、增量式 toggle、聚合回显 |
| v5 | 群聊管理 | groups / group_members、角色、邀请/移除/改名/退出 |
| v6 | 群消息与群已读 | 消息模型会话抽象（dm/group）、群收发/历史/已读 |
| v7 | 附件与图片消息 | 上传端点、内容类型、mime/大小校验、安全回源 |
| v8 | 全文搜索 | 消息全文检索（分页）+ 联系人/群合并检索入口 |
| v9 | 个人资料与头像 | 昵称/简介编辑、头像上传、SSO 同步保护 |
| v10 | 音视频呼叫信令 | WS 呼叫状态机（offer/answer/ICE/reject/end） |

## 通用约定

- WS 写操作仍走 REST（沿用既有约定）；WS 仅承载服务端推送与纯信令（typing / presence /
  call）。信令入站一律校验来源（好友/群成员）、长度与频率上限。
- 所有新 REST 写端点沿用 `get_current_user + require_csrf`；读端点 `get_current_user`。
- 状态码沿用既有约定：400 非法状态、401 未认证、403 越权/CSRF、404 不存在、409 冲突、
  422 参数错误。
- 每版在 `docs/superpowers/plans/2026-08-16-im-roadmap-v<N>.md` 写实施计划（Task、文件、
  TDD 步骤、验收），完成后勾选并同步 CHANGELOG。

## v1 未读计数与已读回执

### 数据模型

新增 `dm_reads`：`user_sub` + `participant_lo` + `participant_hi`（复合 PK，均 FK users.sub
CASCADE）、`last_read_message_id`（BigInteger 变体，默认 0）、`updated_at`。只覆盖单聊；
v6 抽象到群后按会话类型扩展。

### 接口

- `GET /api/conversations`：当前用户所有好友会话摘要，按最后消息时间倒序；每项
  `{peer: Profile, last_message: Message|null, unread_count: int}`。
- `POST /api/conversations/{other_sub}/read`：`{"last_read_id": int>=1}`，upsert 已读游标，
  游标只前进不后退；向对方推 `{"type":"read_receipt","by_sub","peer_sub","last_read_id"}`。
- 发送消息时自动把发送者已读游标推进到新消息 id（自己发的消息不算未读）。

### 语义

未读数 = 会话中 `id > 我的 last_read_id` 且 `sender_sub == 对方` 的消息数。跨端/离线在下次
打开会话列表时可见；实时增量由 WS 推送，重连由客户端重新拉取列表（自愈）。

### 安全影响

已读游标只能由会话参与者写入；`last_read_id` 必须属于该会话（防跨会话污染游标）；游标
只增不减。WS 已读回执只发给会话另一方。

### 验收

未读累计/清零、游标单调、非会话参与者 403/404、`/api/conversations` 排序与摘要正确、
WS 回执定向送达、ruff/mypy/pytest 全绿。

## v2 在线状态与正在输入

### 数据模型

`users.last_seen_at`（可空，登录活动时间；presence 是瞬时态不入库，仅内存）。WS 连接表
本身即在线事实；断开时写 `last_seen_at`。

### 接口与协议

- 连接成功：向全部好友广播 `{"type":"presence","sub","online":true}`；断开（全部连接
  释放后）：`{"type":"presence","sub","online":false,"last_seen_at"}`。
- `GET /api/friends` 响应每项附 `online: bool, last_seen_at: str|null`。
- 客户端 → 服务端 `{"type":"typing","to":<sub>,"action":"start|stop"}`：仅双方为好友时
  中继 `{"type":"typing","from":<sub>,"action":...}`；服务端不落库、不持久。

### 安全影响

presence 只对好友广播（防关系图谱外泄）；typing 校验好友关系，未校验时静默丢弃并计日志；
单客户端对 typing 施加最小间隔限频，防信令放大。

### 验收

上线/下线事件仅好友可见；typing 定向中继、非好友丢弃；`/api/friends` 附在线信息；
断线回写 last_seen；全绿。

## v3 消息编辑与撤回

### 数据模型

`messages` 增 `edited_at`（可空）与 `deleted_at`（可空）。撤回不物理删除：`deleted_at`
标记后 content 清空（或保留原始内容仅不回传，按「清空」实现以减少泄露面），历史返回
`deleted: true` 墓碑。编辑保留 `content` 且回显 `edited_at`。

### 接口

- `PATCH /api/conversations/{other_sub}/messages/{id}`：`{"content"}`，仅发送者、未撤回、
  5 分钟内可编辑；推 `message_edited`（双方）。
- `DELETE /api/conversations/{other_sub}/messages/{id}`：仅发送者、未撤回、5 分钟内；
  推 `message_deleted`（双方）。

### 安全影响

越权（非发送者）403；超窗 409（或 400）；已撤回不可再编辑；历史页对撤回消息仅暴露
`id/created_at/deleted`，不泄露原文；删除时清空 content 列（数据库中不留原文）。

### 验收

编辑/撤回成功与越权/超窗/重复操作矩阵；墓碑不泄露原文；WS 事件定向；全绿。

## v4 表情回应

### 数据模型

新增 `reactions`：`message_id`（FK messages.id CASCADE）+ `user_sub` + `emoji`（复合 PK），
`created_at`。emoji 限定 1–8 个字符（单一 emoji 或 ZWJ 序列），白名单外的返回 422。

### 接口

- `PUT /api/conversations/{other_sub}/messages/{id}/reactions`：`{"emoji"}`，幂等 upsert
  （同一用户同一 emoji 只记一次）；推 `message_reaction`（added）。
- `DELETE .../reactions?emoji=` 或路径参数移除；推 `message_reaction`（removed）。
- 消息载荷（history/WS）附 `reactions: [{emoji, count, me}]` 聚合。

### 安全影响

仅会话参与者可回应（403）；emoji 长度上限防存储滥用；聚合回显不泄露未上榜用户。

### 验收

幂等增/删、聚合计数、非参与者 403、非法 emoji 422、WS 事件、全绿。

## v5 群聊管理

### 数据模型

新增 `groups`：`id`（BigInteger 自增）、`name`（1–64）、`owner_sub`（FK）、`created_at`、
`updated_at`。`group_members`：`group_id` + `user_sub` 复合 PK、`role`
（`owner|admin|member`）、`joined_at`。成员上限与群上限常量（如单群 200、单用户可无限制，
本期不设总闸但预留常量）。

### 接口

- `POST /api/groups`：`{name, member_subs: [..]}`，创建者即 owner；初始成员必须全为好友。
- `GET /api/groups`：我加入的群 + 成员/角色/最后消息摘要（v6 前无消息）。
- `GET /api/groups/{id}`：详情（仅成员）。
- `PATCH /api/groups/{id}`：改名，owner 或 admin。
- `POST /api/groups/{id}/members`：邀请，owner/admin；被邀者必须为邀请人好友（项目是熟人
  小圈子，群成员准入以「邀请人与目标为好友」为闸）。
- `DELETE /api/groups/{id}/members/{sub}`：移除，owner/admin（admin 不得移除 owner 或其他
  admin，owner 可移除 admin）。
- `POST /api/groups/{id}/leave`：非 owner 退出；owner 需先转让或解散。
- `POST /api/groups/{id}/transfer`：owner 转让给群内成员。
- 全量推 `group_event` 给受影响成员（created/renamed/member_joined/member_removed/
  member_left/owner_changed）。

### 安全影响

成员可见性仅限群内；角色权限矩阵服务端强校验（非 owner 不得转让/解散）；好友闸限制
群扩张；成员数上限防膨胀。

### 验收

角色矩阵（owner/admin/member × 各操作）、邀请非好友 403、移除规则（admin 不可移除
admin/owner）、转让/退出、非成员不可见、全绿。

## v6 群消息与群已读

### 数据模型（会话抽象迁移）

`messages` 增 `conversation_type`（`dm|group`，默认 dm）与 `group_id`（可空 FK）。DM 行为
保持既有 `sender_sub/recipient_sub/participant_lo/hi`；群消息 `sender_sub` 为发送者、
`group_id` 指向群、`recipient_sub` 置空由约束允许（改造原非空/自环约束，DM 校验移到
service 层）。SQLite 走 `_ensure_message_columns` 兼容迁移；PostgreSQL 未来 Alembic。
`conversation_reads` 泛化：`user_sub + conversation_type + conversation_id`（dm 用
`participant_lo:hi` 字符串键、group 用 group_id）+ `last_read_message_id`。

### 接口

- `POST /api/groups/{id}/messages`：`{content}`，仅成员；向全群推 `message`（附 group 上下文）。
- `GET /api/groups/{id}/messages`：倒序游标分页（同 DM 语义）。
- `POST /api/groups/{id}/read`：群已读游标；向群成员推 `read_receipt`（附 `group_id`）。
- `GET /api/conversations`：合并 DM 与群摘要，`peer` 或 `group` 二选一出现。

### 安全影响

仅成员可发/读群消息；群已读游标只前进；`/api/conversations` 不泄露已退出群的历史。

### 验收

群收发/历史/分页、非成员 403、群未读计数（排除自己消息）、退群后不可见、迁移兼容
（旧 DM 数据仍可读）、全绿。

## v7 附件与图片消息

### 数据模型与存储

消息 `content_type`（`text|image|file`，默认 text）、`attachment_name/size/mime/url`
可空列。上传：`POST /api/uploads`（multipart，`LICHAT_UPLOAD_MAX_MB` 默认 10，上限 20）；
存储目录 `data/uploads/<yyyymm>/<random>.<ext>`（随机文件名防遍历）。mime 白名单
（image/jpeg、image/png、image/webp、image/gif、text/plain、application/pdf 等），
SVG/HTML 类拒绝。消息发送复用 `/api/conversations/{sub}/messages` 与群消息端点，扩展
`content_type` 与 attachment 元数据；附件必须来自本人上传（服务端记录 owner）。

### 接口

- `POST /api/uploads`（multipart `file`）→ `{id,url,name,size,mime}`（uploads 表记录 owner）。
- `GET /api/uploads/{name}`：会话鉴权后回源；图片 `Content-Disposition: inline` 且
  `X-Content-Type-Options: nosniff`，下载类附件 `attachment` 与安全文件名。
- 消息载荷回显 attachment 元数据（不回传绝对 URL 之外的敏感信息）。

### 安全影响

扩展名由内容决定（按检测 mime 落盘，不信任客户端文件名）；大小与类型双重校验；随机
文件名 + 只读回源端点做会话鉴权（不允许匿名直连）；拒绝 SVG/HTML 防存储型 XSS；
回源 `nosniff`；上传限频（每会话窗口计数）。

### 验收

合法图片/文件上传回源、超限 413/422、非法 mime 拒绝、非上传者引用 403、匿名访问 401、
SVG 拒绝、全绿。

## v8 全文搜索

### 接口

- `GET /api/search?q=&kind=messages|contacts&before=&limit=`：
  - messages：检索我参与的会话（DM 双方 / 群成员）内容，LIKE 不区分大小写，倒序游标
    分页，返回 `{id, conversation, snippet, created_at}`（snippet 前后截断、脱敏长度上限）。
  - contacts：复用 `/api/users/search` 的语义并回传 friend_status。
- 结果上限（≤50），q 1–64 字符。SQLite 用 LIKE（小圈子规模）；PostgreSQL 后续可换
  `ilike`/FTS（本版在 service 抽象检索函数，便于替换）。

### 安全影响

只搜自己可见范围（DM 参与者 / 群成员）；不回传非参与会话内容；snippet 长度受限防结果页
信息倾泻。

### 验收

命中/未命中/越界会话、分页终止、kind 过滤、权限边界（非群成员搜不到群消息）、全绿。

## v9 个人资料与头像

### 数据模型

`users.bio`（可空 ≤200）。`PATCH /api/me`：`{nickname, bio}`（nickname 1–32 strip）。
头像复用上传：`POST /api/me/avatar`（multipart 或引用 upload id），写入 `users.picture`
（本地 `/api/uploads/...` 相对路径）；SSO 同步保护：userinfo 仅在 `picture` 为空时回填，
本地头像一旦设置不被 IdP 覆盖（昵称同理：仅空时回填）。

### 安全影响

nickname/bio 长度与可见性（bio 仅好友可见；搜索不回传 bio）；头像必须为白名单图片 mime；
更新走 CSRF；`/api/me` 与 profile 回显 sanitize。

### 验收

编辑昵称/简介、SSO 不覆盖本地值、头像上传回源、非法 mime 拒绝、非图片 422、全绿。

## v10 音视频呼叫信令

### 协议（仅信令，媒体走 WebRTC P2P，服务端不中转流）

客户端 → 服务端：`{"type":"call","op":"offer|answer|ice|reject|end","to":<sub>,
"payload":{...}}`（payload 大小上限，如 16KB；ICE 限频）。服务端校验双方为好友后原样中继
`{"type":"call","op":...,"from":<sub>,"payload":{...}}`。状态机：`idle → ringing →
connected → ended`；`reject/end` 终结；重复 offer 在 ringing 期间拒绝（409 事件）；
呼叫中目标离线返回 `call_unavailable`。呼叫元数据（SDP 等）不落库、不记日志。

### 安全影响

仅好友间呼叫；信令大小/频率上限防滥用；日志零 SDP；离线即终止不再中继；群呼叫本期
不做（v10 仅 1:1，留扩展点）。

### 验收

offer→answer→ice→end 全链路定向中继、非好友丢弃、超限丢弃、状态机非法迁移拒绝、全绿。

## 收尾

- 每版：计划文件、实现、失败测试→实现→全绿、独立 `feat:` 提交、CHANGELOG 分区、docs 同步。
- v10 完成后：README 路线图勾选对应里程碑、架构图与 api/security 全量复查、一次最终全量
  验证（pytest/ruff/mypy + 本地冒烟 `curl /healthz`），向用户交付路线图与验收汇总。
