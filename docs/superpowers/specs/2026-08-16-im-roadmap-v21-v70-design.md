# Li&Chat 体验与业务扩展路线图（v21–v70）设计规格

日期：2026-08-16
分支：`codex/im-roadmap-v21-v70`
前置：[v1–v10](2026-08-16-im-roadmap-v1-v10-design.md)、
[v11–v20](2026-08-16-im-roadmap-v11-v20-design.md)（均已交付，213 测试全绿）

## 目标

在 v1–v20 的 IM 功能底座之上，自主迭代 50 个版本，三线并进：

1. **前端体验优化**（v21–v30）：错误反馈、断线重连、消息阅读体验、上传体验、通知与快捷键。
2. **业务新功能**（v31–v40）：备注名、禁言、解散、语音消息、群文件、批量转发、投票、已读明细、
   通知中心、申请附言。
3. **完善已有业务与逻辑闭环**（v41–v60）：草稿、重试、归档、仅自己删除、二次确认、导出、帮助；
   重连补拉、竞态防护、边界态、限流、端到端回归。
4. **收口**（v61–v70）：无障碍、性能、可观测性、安全、部署、文档、设计系统、兼容性与发布。

**原则不变**：安全不降级；测试零外网；路由薄、业务进 service；每版独立验收
（pytest / ruff / mypy 全绿）与独立提交；CHANGELOG 与受影响 docs 同步。

## 现状盘点（基线 213 测试全绿）

已有：SSO、好友、单聊/群聊、未读/已读、presence/typing、编辑/撤回、表情、附件、搜索、资料/头像、
1:1 呼叫、引用/转发/提及/收藏/置顶/免打扰、群公告/头像、登录限流、会话管理、通话记录。

已知体验缺口（本路线图覆盖）：API 失败普遍静默无反馈；WS 断开不自动重连且不补拉消息；
搜索命中不定位到具体消息；图片无查看器；上传无进度；消息无发送状态；高风险操作无确认；
大量空态/错误态缺失；页面标题无未读角标；无快捷键体系；消息列表无日期分组。

## 版本总览与依赖

各版本严格串行（共享 `models.py` / `main.py` / WS 协议 / docs / CHANGELOG，零文件重叠不可
并行）。每版产出：契约/实现 + 测试 + 必要前端增量 + 文档同步。

| 版本 | 主题 | 关键交付 |
| --- | --- | --- |
| v21 | 全局 Toast 与错误反馈 | toast 系统、api() 统一错误解析、替换 alert |
| v22 | WS 自动重连 | 指数退避、在线状态、重连后刷新 |
| v23 | 日期分组与连续消息合并 | 分隔线、同作者合并头像/昵称 |
| v24 | 图片查看器 | 全屏遮罩、ESC/点击关闭 |
| v25 | 粘贴/拖拽上传与多选发送 | paste/drop/multiple 批量 |
| v26 | 上传进度条 | XHR progress + 取消 |
| v27 | 搜索命中定位与高亮 | 跳转滚动 + 闪烁高亮 |
| v28 | 本地会话过滤与骨架屏 | 列表过滤、空态/加载态统一 |
| v29 | 标题未读角标与通知偏好 | 标题计数、浏览器通知开关 |
| v30 | 快捷键与帮助 | Ctrl+K 搜索、Ctrl+Enter 发送、快捷键帮助 |
| v31 | 好友备注名 | friendships.remark、显示优先备注 |
| v32 | 群成员禁言 | group_members.muted、发消息 403、前端开关 |
| v33 | 群解散 | owner 专属、级联清理、二次确认 |
| v34 | 语音消息 | audio 上传白名单、录制、播放气泡 |
| v35 | 群文件面板 | 附件聚合分页、下载 |
| v36 | 消息多选批量转发 | 多选模式、逐条转发反馈 |
| v37 | 群投票 | poll/votes、投票消息卡片、关闭 |
| v38 | 群已读明细 | 已读成员列表、气泡「N 人已读」 |
| v39 | 通知中心 | notifications 表、未读角标、WS 推送 |
| v40 | 好友申请附言 | friendships.reason、申请卡片展示 |
| v41 | 会话草稿 | localStorage 自动保存/恢复 |
| v42 | 发送状态与失败重试 | pending/sent/failed、重试按钮 |
| v43 | 会话归档 | settings.archived、归档列表 |
| v44 | 消息仅自己删除 | user_message_deletes、历史过滤 |
| v45 | 高风险操作二次确认 | 统一确认弹窗 |
| v46 | 群公告时间与空态 | announcement_updated_at、引导文案 |
| v47 | 上传失败重试与提示 | 失败 toast + 重试、限制文案 |
| v48 | 输入框表情面板 | emoji 分类面板插入 |
| v49 | 我的数据导出 | GET /api/me/export JSON 下载 |
| v50 | 帮助与关于 | 版本/快捷键/路线图弹窗 |
| v51 | 重连增量补拉 | 重连后 gap 检测与补齐 |
| v52 | 免打扰未读徽标 | 灰徽标、标题计数仍生效 |
| v53 | 已读回执一致性 | 群退群清理、游标边界 |
| v54 | 空态/错误态全覆盖 | 5xx toast + 重试、列表空态 |
| v55 | 相对时间显示 | 会话列表相对时间 + tooltip |
| v56 | 输入校验前后端对齐 | 即时长度反馈、超长截断提示 |
| v57 | 多标签页协同 | storage 事件同步登出/主题 |
| v58 | 请求竞态防护 | 会话切换丢过期响应 |
| v59 | 群事件 UI 收敛 | 被移除/解散即收敛 + 提示 |
| v60 | 端到端场景回归 | 全链路 pytest 场景测试 |
| v61 | 无障碍收口 | focus trap、ARIA、键盘导航、对比度 |
| v62 | 后端查询优化 | 未读计数聚合、摘要 N+1 消解 |
| v63 | 前端渲染性能 | 分批渲染、图片占位、懒加载 |
| v64 | 可观测性 | 慢请求日志、healthz 扩展 |
| v65 | 安全限流收口 | 发送/编辑/上传频率限制 |
| v66 | 部署收口 | PostgreSQL 兼容验证、compose 注解 |
| v67 | 文档全量同步 | README/CHANGELOG/docs 对齐 |
| v68 | 设计系统审计 | 令牌一致性、重复样式清理 |
| v69 | 兼容性细节 | 安全区、dvh、移动端细节 |
| v70 | 发布收口 | v1.0.0、发布 CHANGELOG、最终验收 |

## 通用约定

- 所有新 REST 写端点沿用 `get_current_user + require_csrf`；读端点 `get_current_user`。
- 状态码沿用既有约定：400 非法状态、401 未认证、403 越权/CSRF、404 不存在、409 冲突、
  422 参数错误、429 限流。
- 前端测试沿用内容契约测试（`tests/test_frontend.py` 风格：断言关键 id/类/端点/行为标记）；
  后端改动必配行为测试。纯视觉细节不做像素断言。
- SQLite 兼容迁移：新列走 `_ensure_*_columns` 模式；PostgreSQL 未来 Alembic 承担。
- 每版在 `docs/superpowers/plans/2026-08-16-im-roadmap-v21-v70.md` 勾选 TDD 步骤。

## 阶段一：前端体验优化（v21–v30）

### v21 全局 Toast 与错误反馈

- `static/app.js` 增 `toast(message, kind)`（info/success/error，aria-live，自动消退，可叠加）。
- `api()` 非 2xx 时解析 `detail` 并 toast，5xx 显示「服务异常，请稍后重试」；移除 `window.alert`。
- 关键操作成功后 toast 反馈（发送成功不需要，编辑/撤回/收藏/转发等轻量反馈）。
- 验收：`/app.js` 含 `toast(`、`aria-live`、无 `window.alert`；style 含 `.toast`。

### v22 WS 自动重连

- 客户端断线（非 4401、非登出）按 1s/2s/4s/…/30s 上限指数退避重连，页面 `visibilitychange`
  恢复可见时立即重连。
- 重连成功：状态提示「已重新连接」+ `refreshSidebar()`；活动会话在 v51 前先 `loadHistory()`。
- 验收：契约测试断言 `backoff`、`visibilitychange`、重连函数存在；4401 仍跳登录。

### v23 日期分组与连续消息合并

- 消息列表按天插入日期分隔线（今天/昨天/M月D日/含年份）。
- 相邻消息（同作者、间隔 <5 分钟、同日）合并展示：仅首条显示头像与昵称。
- 验收：`/app.js` 含日期分隔与 `message-merged` 标记；style 含对应类。

### v24 图片查看器

- 点击图片消息打开全屏遮罩（原图、深色背景、关闭按钮、ESC/点击遮罩关闭）。
- 验收：`/app.js` 含 `image-viewer` 打开/关闭逻辑；style 含 `.image-viewer`。

### v25 粘贴/拖拽上传与多选发送

- composer 支持 `paste`（图片直接上传发送）、`drop`（文件拖入上传）、`<input multiple>` 多选
  逐个上传发送。
- 验收：`/app.js` 含 `paste`/`dragover`/`drop` 处理与 `multiple`。

### v26 上传进度条

- 上传改用 XHR 上报 progress，composer 上方显示进度条（百分比 + 取消）。
- 验收：`/app.js` 含 `XMLHttpRequest` 与 `upload.progress` 事件；style 含 `.upload-progress`。

### v27 搜索命中定位与高亮

- 消息搜索命中点击后打开会话并定位到该消息（向后拉历史直到出现），进入时闪烁高亮。
- 验收：`/app.js` 含 `locateMessage`/`scrollIntoView`；style 含 `.message-flash`。

### v28 本地会话过滤与骨架屏

- 好友/群列表顶部本地过滤输入（或复用搜索框）；列表加载中显示骨架屏（shimmer）。
- 空态文案统一（无好友/无群/无申请/无推荐/无消息/搜索无结果）。
- 验收：`/app.js` 含 `skeleton` 类；style 含 shimmer 动画。

### v29 标题未读角标与通知偏好

- 未读总数写入 `document.title`（`(3) Li&Chat`）；新消息且页面不可见时按偏好发
  `Notification`（需授权，localStorage 开关「桌面通知」）。
- 验收：`/app.js` 含 `document.title`、`Notification`；设置入口存在。

### v30 快捷键与帮助

- Ctrl/Cmd+K 聚焦搜索、Ctrl/Cmd+Enter 发送、Esc 关弹层/退出编辑；`?` 打开快捷键帮助弹窗。
- 验收：`/app.js` 含 `keydown` 组合键处理与帮助弹窗文案。

## 阶段二：业务新功能（v31–v40）

### v31 好友备注名

- `friendships.remark`（可空 ≤32）；`PATCH /api/friends/{sub}/remark`（好友关系内）。
- 好友列表/会话/消息对端展示优先备注名；仅本人可见；`friend_event` 附 remark 变更（简化：
  本地刷新即可，不做广播）。
- 验收：设置/清除备注、非好友 404、长度校验；前端备注入口（好友行菜单或聊天头部）。

### v32 群成员禁言

- `group_members.muted`（布尔，默认 False）；`PATCH /api/groups/{id}/members/{sub}/mute`
  `{"muted":bool}`（owner/admin；不得禁言 owner/admin 与自己）。
- 被禁言成员发群消息 403 `"muted"`；WS `group_event` `member_muted`；前端成员行禁言开关与
  输入框禁用态。
- 验收：禁言/解除、权限矩阵、发消息 403、事件广播。

### v33 群解散

- `POST /api/groups/{id}/dissolve`（仅 owner）；删除群后级联清理 members/messages/reads/
  conversation_settings 孤儿键；WS `group_event` `dissolved` 广播全体后断链。
- 前端解散入口（owner）+ 二次确认（v45 之前先用内置 confirm，后续换统一弹窗）。
- 验收：仅 owner、级联清理、成员随后访问 404、广播。

### v34 语音消息

- 上传白名单增 `audio/webm`、`audio/mp4`（嗅探 EBML/`ftyp`）；`content_type: "audio"`。
- 前端按住录音（MediaRecorder）→ 上传 → 消息气泡 `<audio controls>`。
- 验收：audio 上传合法、伪造拒绝、audio 消息校验、前端播放器。

### v35 群文件面板

- `GET /api/groups/{id}/files?cursor=&limit=`：群内 file/audio 附件消息倒序分页。
- 前端群详情「文件」分区列表（文件名/大小/发送者/时间），点击下载。
- 验收：仅成员、分页、聚合正确；前端入口。

### v36 消息多选批量转发

- 消息长按/按钮进入多选模式；选中后「转发」批量打开目标选择，逐条调用既有 forward 接口，
  展示进度 toast。
- 验收：`/app.js` 含多选状态与批量转发调用。

### v37 群投票

- `polls`（id/group_id/creator_sub/question/options JSON/multiple/closed/created_at）与
  `poll_votes`（poll_id+user_sub 复合 PK，option_index JSON，可多选）。
- 消息 `content_type="poll"` + `poll_id`；发送端点扩展 `poll` 参数（问题 1–120、选项 2–10、
  每项 1–60）；`PUT /api/groups/{id}/polls/{pid}/vote`（成员、未关闭、选项合法）、
  `POST .../close`（创建者或 owner/admin）；载荷附 poll 详情与 my_vote；WS `poll_event`
  （created/voted/closed）群内广播。
- 前端投票卡片（选项、百分比条、投票/关闭按钮）。
- 验收：创建/投票/改票/关闭/越权矩阵、群内广播、已关闭禁投。

### v38 群已读明细

- `GET /api/groups/{id}/messages/{mid}/reads`：返回已读成员（游标 ≥ mid）名单（仅成员）。
- 群消息气泡（自己的消息）附「N 人已读」，点击弹名单。
- 验收：游标口径、成员校验、名单正确。

### v39 通知中心

- `notifications`（id/user_sub/type/actor_sub/group_id/payload/read_at/created_at）；
  `GET /api/me/notifications?cursor=`、`POST /api/me/notifications/read`（全部已读）。
- 事件源：好友申请、@提及、禁言/解除、角色变更、群解散；WS `notification` 定向推送；
  前端铃铛 + 未读角标 + 列表 + 跳转。
- 验收：各事件落账、未读计数、已读、越权 404、WS 推送。

### v40 好友申请附言

- `friendships.reason`（≤200）；`POST /api/friends/requests` 加 `message`；申请载荷附 reason。
- 前端发申请弹层附言输入；申请卡片展示附言。
- 验收：长度校验、载荷回显、卡片展示。

## 阶段三：完善已有业务（v41–v50）

### v41 会话草稿

- 输入变化时按会话键存 localStorage；打开会话恢复；发送/清空后删除。
- 验收：`/app.js` 含 `draft:` 前缀存取。

### v42 发送状态与失败重试

- 消息本地对象含 `status`（pending/sent/failed）；发送中气泡半透明 + 转圈；失败红色 + 重试按钮。
- 验收：`/app.js` 含 `message-sending`/`message-failed` 与重试处理；style 含对应类。

### v43 会话归档

- `user_conversation_settings.archived`；`PATCH /api/conversations/settings` 扩展 archived；
  `GET /api/conversations?archived=true|false` 过滤。
- 前端会话行「归档」操作与「已归档」分区。
- 验收：设置/过滤/归属校验；前端入口。

### v44 消息仅自己删除

- `user_message_deletes`（user_sub+message_id）；`DELETE /api/conversations/{sub}/messages/{id}/me`
  与群版本；历史/摘要载荷对已删者过滤；不推 WS（下次加载生效）。
- 验收：删除后历史不可见、对方仍可见、越权边界。

### v45 高风险操作二次确认

- 统一 `confirmModal(title, message, action)`：退出群、解散群、移除成员、删除好友、退出登录。
- 验收：`/app.js` 含 `confirmModal` 且上述操作走确认。

### v46 群公告时间与空态

- `groups.announcement_updated_at`；公告横幅显示发布时间；空公告显示引导文案。
- 验收：模型列 + 载荷；前端展示。

### v47 上传失败重试与提示

- 上传失败 toast（类型/大小/网络原因区分）+ 重试按钮保留文件。
- 验收：`/app.js` 含 `upload-failed` 处理。

### v48 输入框表情面板

- 表情按钮打开分类面板（常用/笑脸/手势/符号），点击插入光标处。
- 验收：`/app.js` 含 `emoji-panel` 与插入逻辑；style 含面板样式。

### v49 我的数据导出

- `GET /api/me/export`：JSON 下载（资料/好友/单聊与群消息/群信息/收藏），`Content-Disposition`
  附件；不含他人不可见内容。
- 验收：内容完整性 + 边界（仅自己可见范围）+ 前端入口。

### v50 帮助与关于

- `/api/version` 扩展 `app_version`；「关于」弹窗显示版本、路线图、快捷键；帮助入口。
- 验收：版本端点字段 + 前端弹窗。

## 阶段四：逻辑闭环（v51–v60）

### v51 重连增量补拉

- 重连成功后对活动会话执行 gap 检测：本地最新 id 与远端对比，缺失消息补拉并合并渲染。
- 验收：`/app.js` 含 `reconcileMessages`；测试断言函数存在与调用。

### v52 免打扰未读徽标

- 免打扰会话显示灰色未读徽标（仍计数）；标题计数包含全部未读。
- 验收：`/app.js` 徽标渲染条件变化；style 含 `.badge-muted-unread`。

### v53 已读回执一致性

- 退群/解散清理 `group_reads`（已有 FK CASCADE，验证并补测试）；游标只前进补边界测试。
- 验收：退群后无残留、跨会话游标拒绝。

### v54 空态/错误态全覆盖

- 5xx/网络错误统一 toast + 列表重试按钮；所有列表空态文案 + 图标。
- 验收：契约测试覆盖各空态 id/文案。

### v55 相对时间显示

- 会话列表摘要用相对时间（刚刚/x分钟前/x小时前/昨天/M月D日），hover 显示完整时间。
- 验收：`/app.js` 含 `relativeTime`；tooltip 属性。

### v56 输入校验前后端对齐

- 前端即时显示剩余字数/超长提示；粘贴超长自动截断并提示。
- 验收：`/app.js` 含 `maxlength` 提示逻辑。

### v57 多标签页协同

- `storage` 事件：其他标签登出/登录、主题切换同步到本标签。
- 验收：`/app.js` 监听 `storage` 并处理主题/登出键。

### v58 请求竞态防护

- 会话切换/加载序列号，过期响应丢弃（`state.conversationEpoch`）。
- 验收：`/app.js` 含 epoch 比较。

### v59 群事件 UI 收敛

- `member_removed`（我）、`dissolved`、`owner_changed` 事件：立即收敛面板/刷新并 toast。
- 验收：`/app.js` 处理上述事件并提示。

### v60 端到端场景回归

- `tests/test_e2e_flow.py`：两用户从添加好友→单聊→建群→投票→禁言→解散全链路（ASGI 传输 +
  WS 事件断言）。
- 验收：场景测试全绿。

## 阶段五：收口（v61–v70）

### v61 无障碍收口

- 弹层 focus trap + 关闭还原焦点；`aria-modal` 全覆盖；键盘导航（Tab 可达、Esc 关闭）；
  对比度检查与修复。
- 验收：契约测试断言 focus/aria 标记。

### v62 后端查询优化

- 未读计数改 SQL 聚合（避免全量消息扫描）；会话摘要减少 N+1。
- 验收：行为不变 + 测试全绿。

### v63 前端渲染性能

- 消息分批渲染（每次 ≤100 条）、图片宽高占位、原生懒加载。
- 验收：`/app.js` 含批渲染标记；性能冒烟（本地）。

### v64 可观测性

- 慢请求（>500ms）结构化日志；`/healthz` 返回 db 状态与版本。
- 验收：日志输出存在；healthz 字段。

### v65 安全限流收口

- 发消息/编辑/上传按用户滑动窗口限流（`LICHAT_ACTION_RATE_*` 配置），429 + Retry-After。
- 验收：次数边界与窗口复位。

### v66 部署收口

- PostgreSQL 兼容验证（可选 env 测试或文档）；compose 生产注解与健康检查增强。
- 验收：文档与 compose 更新。

### v67 文档全量同步

- README 测试数/功能清单/路线图、CHANGELOG、architecture/api/security/deployment 对齐；
  新增用户指南（docs/user-guide.md）。
- 验收：文档与代码一致（手动核对 + 测试数量同步）。

### v68 设计系统审计

- style.css 令牌一致性检查、重复样式合并、暗色对比修复；MASTER.md 同步。
- 验收：样式契约测试仍绿 + 手动审计清单。

### v69 兼容性细节

- iOS 安全区（env(safe-area-inset-*)）、`100dvh`、长按菜单、preview 图刷新。
- 验收：样式含安全区/dvh 标记。

### v70 发布收口

- `pyproject.toml` 版本 v1.0.0、FRONTEND_VERSION 同步、CHANGELOG 发布分区、
  最终全量门禁 + 本地冒烟（`curl /healthz`）+ 汇总报告。
- 验收：全绿 + 冒烟输出。

## 收尾

- 每版：写失败测试 → 验证红 → 最小实现 → 验证绿 → 独立提交（`feat:`/`fix:`/`perf:`/`docs:`）。
- 每版同步 CHANGELOG 与受影响 docs（api/architecture/security/deployment）。
- v70 后：README 路线图勾选、最终全量验证（pytest/ruff/mypy + 本地冒烟），合并 main，
  向用户交付 50 版验收汇总。
