# Li&Chat 主流 IM 功能路线图（v11–v20）设计规格

日期：2026-08-16
分支：`codex/im-roadmap-v11-v20`
前置：[v1–v10 路线图](2026-08-16-im-roadmap-v1-v10-design.md)（已交付：SSO、好友、
单聊/群聊、未读/已读、presence/typing、编辑/撤回、表情、附件、搜索、资料/头像、1:1 呼叫信令）

## 目标

第二轮 10 个版本：补齐主流 IM 的会话增强能力（引用、转发、提及、收藏、置顶/免打扰）、群
管理深化（公告/头像、群消息操作补齐），并收口安全与账号治理（登录限流、会话管理、呼叫
记录）。

**原则不变**：安全不降级；测试零外网；路由薄、业务进 service；每版独立验收（pytest / ruff /
mypy 全绿）与独立提交；CHANGELOG 与受影响 docs 同步。

## 版本总览与依赖

各版本严格串行（共享 `models.py` / `main.py` / WS 协议 / docs / CHANGELOG）。每版产出：
后端契约 + 测试 + 必要前端增量 + 文档同步。

| 版本 | 主题 | 关键交付 |
| --- | --- | --- |
| v11 | 消息引用回复 | reply_to 校验、引用预览（截断、防递归）、前端回复栏 |
| v12 | 消息转发 | 跨会话转发（可见范围校验）、forwarded 标记、前端目标选择 |
| v13 | @提及 | message_mentions 表、成员校验、WS 提及、前端 @ 选择器 |
| v14 | 收藏消息 | user_stars、幂等 star/unstar、收藏列表、载荷 starred 标记 |
| v15 | 置顶与免打扰 | user_conversation_settings、排序与静音、前端开关 |
| v16 | 群公告与群头像 | groups.announcement/avatar_url、owner/admin 维护、前端横幅 |
| v17 | 群消息操作补齐 | 群编辑/撤回/表情（复用单聊语义，群内广播） |
| v18 | 登录限流 | 进程内滑动窗口（IP 粒度）、429 + Retry-After |
| v19 | 会话管理 | 会话列表/撤销/退出其他设备、WS 会话级断开 |
| v20 | 呼叫记录 | call_logs（missed/accepted/rejected）、历史列表、WS 流程落账 |

## v11 消息引用回复

- `messages.reply_to_id`（可空 FK messages.id）；引用目标必须同会话（单聊同 pair / 群同
  group_id）；引用已撤回消息允许（预览显示墓碑）。
- 载荷 `reply_to`：`{id,sender_sub,content(≤100 截断),deleted,content_type}`，不递归嵌套。
- 发送接口（单聊/群）加 `reply_to_id`；校验失败 404/422。
- 前端：消息「回复」按钮 → 输入框上方引用条，可取消。

## v12 消息转发

- 目标会话：`POST /api/conversations/{sub}/forward` 与 `POST /api/groups/{id}/forward`，
  请求 `{"message_id":n}`；源消息必须在转发者可见范围（单聊双方 / 群成员），已撤回 409。
- 新消息复制 content/content_type/attachment 元数据并置 `forwarded=true`；WS 正常推送。
- 前端：消息「转发」按钮 → 目标选择弹层（好友 + 我的群）。

## v13 @提及

- `message_mentions`（message_id + user_sub 复合 PK，FK CASCADE）。
- 发送接口加 `mentions:[sub]`：单聊仅允许对方，群仅允许群成员；去重；上限 50。
- 载荷与 WS 事件附 `mentions`；被提及用户收到 `mention` 高亮（前端展示 @我 样式）。
- 前端群 composer「@」按钮列出成员插入提及，发送时携带 sub。

## v14 收藏消息

- `user_stars`（user_sub + message_id 复合 PK、created_at）。
- `PUT/DELETE /api/messages/{id}/star`（幂等）；校验消息在自己可见范围。
- `GET /api/me/stars?cursor=`（倒序游标 ≤50）返回消息 + 会话引用（同搜索结构）。
- 历史/载荷附 `starred`（按查看者）。

## v15 置顶与免打扰

- `user_conversation_settings`（user_sub + kind(dm/group) + key 复合 PK；pinned/muted 布尔）。
  key：单聊用 pair 排序键，群用 group_id 字符串。
- `PATCH /api/conversations/settings` `{"kind","key","pinned","muted"}` upsert。
- `GET /api/conversations` 附 pinned/muted；置顶会话排在前面。
- 前端：会话行菜单（置顶/取消置顶、免打扰开关）；免打扰时不弹未读徽标样式。

## v16 群公告与群头像

- `groups.announcement`（Text 可空 ≤2000）、`groups.avatar_url`（String 可空）。
- `PATCH /api/groups/{id}/announcement`（owner/admin）；`POST /api/groups/{id}/avatar`
  `{"url"}`（本人图片上传，owner/admin）；WS `announcement_updated/avatar_updated`。
- GroupOut 附 announcement/avatar_url；前端群详情横幅与编辑入口、头像设置。

## v17 群消息操作补齐

- `PATCH/DELETE /api/groups/{id}/messages/{mid}`（发送者、5 分钟窗、墓碑；群内广播
  message_edited/message_deleted）。
- `PUT/DELETE /api/groups/{id}/messages/{mid}/reactions`（成员校验；群内广播
  message_reaction）。
- 群历史附 reactions/my_reactions；前端解除群消息对编辑/撤回/表情的禁用。

## v18 登录限流

- 进程内滑动窗口（`LICHAT_LOGIN_RATE_LIMIT`，默认 10 次/60 秒，IP 粒度），作用于
  `/oidc/login` 与 `/oidc/callback`；超限 429 + `Retry-After`。
- 429 响应不泄露具体策略细节；测试断言次数边界与窗口复位（短窗口测试配置）。

## v19 会话管理

- ConnectionManager 按连接记录 session_id；`disconnect_session(sub, session_id)`。
- `GET /api/me/sessions`（id、created_at、last_seen_at、expires_at、current）。
- `DELETE /api/me/sessions/{id}`（撤销我的某个会话并断其 WS；撤销当前会话等同登出）；
  `DELETE /api/me/sessions`（撤销除当前外全部会话）。
- 前端：个人菜单「登录设备」列表 + 撤销按钮 + 「退出其他设备」。

## v20 呼叫记录

- `call_logs`（caller_sub、callee_sub、kind(audio/video)、status(missed/accepted/rejected)、
  started_at、ended_at）。
- WS 呼叫流程落账：offer 建 started；answer→accepted；reject→rejected；end→终态结束时间；
  离线/忙线记 missed（仅呼叫方视角）；重开呼叫写新行。
- `GET /api/me/calls?cursor=`（倒序 ≤50，附对端资料）；前端「通话记录」列表。

## 收尾

每版独立计划文件、TDD、全绿、独立提交、CHANGELOG/docs 同步；v20 后全量门禁 + 本地冒烟，
更新 README 路线图，向用户交付第二轮路线图与验收汇总。
