# Changelog

## 未发布（开发中）

### 缺陷修复

- 音视频呼叫信令修复：offer 中继透传 `kind`（来电可区分视频/语音，语音来电不再请求
  摄像头）；被叫端响铃期间缓存主叫 ICE 候选、主叫端 answer 后统一注入（修复 ICE 候选
  丢失导致「已接通」却无媒体）；远程视频显式 `play()` 兜底自动播放拦截
- 呼叫 ICE 限频不再给发送方回 `invalid`：超限静默丢弃（修复 trickle ICE 连发候选触发
  「呼叫失败」并自挂断）
- 修复 `--chat-surface-1` 未定义导致弹层卡片背景透明（统一回退到 `--chat-surface`）

### 功能

- 可配置 WebRTC ICE 服务器：`LICHAT_RTC_ICE_SERVERS`（JSON 数组，stun/stuns/turn/turns
  前缀、≤8 个，非法值拒绝启动），列表随 `GET /api/me` 的 `ice_servers` 下发；跨网通话
  可接入 STUN/TURN（默认空 = 仅同网/直连）
- 双语义登出：新增 `POST /oidc/logout-local`（仅退出本网站，清本地会话并断 WS，不触发
  SSO）；退出登录弹窗提供「仅退出本网站 / 退出 SSO」两个选项，对齐 Li&Pass 指南 §8.1
- 设计系统同步 Li-Design 模板 V1.2：主按钮改半透明单色着色 + 细描边 + `::after` 扫光
  （4s，disabled 关闭），认证卡与 Logo 呼吸辉光（4.5s，reduced-motion 静止）；槽位表
  20 → 22；预览基线六张全部重拍
- 全量采纳 Li-Design V1.2 海玻璃配色方案：浅色全淡色（bg `#F6FBF9`、主色 `#25786D`、
  雾面中性色）+ 深色 D1 雾灰中间调（bg `#3A3F45`、主色 `#7FD4C6`）+ secondary 与六强调
  色板（ice/aqua/lilac/sage/mint/sand 明暗两套）+ 水绿 tint 阴影；品牌位/首帧主题同步

### 安全加固

- id_token 校验新增 `at_hash` 核对（`base64url(SHA256(access_token) 左 16 字节)`，
  缺失/不符即拒绝登录），补齐 Li&Pass V2 接入验收清单「id_token 校验完整」
- token 端点 403 黑名单按 RFC 6749 新格式 `error=access_denied` 映射封禁提示，不再
  误报「登录凭证已失效」
- 账号绑定规则文档化并补回归测试：`sub`（openid 主体标识）是唯一可信标识、`email` 为
  可变属性；本地仅按 `sub` upsert、每次登录刷新 email，「换邮箱不新建账号」

### 行为变更

- ICE 限频默认最小间隔由 50ms 放宽至 10ms（仍为每对呼叫粒度的滥用防护）
- Li&Pass 发现文档 issuer 与五个端点已收敛为 https 字面值；本端 http→https 升级逻辑
  保留为防御性兜底（当前为 no-op），`iss` 仍按发现文档原文严格校验
- 海玻璃落地按模板附录 E 做 RGB 调校：muted/success/warning/destructive 四处同色相加深
  至 ≥4.5:1；深色带文字的软底改用实色粉彩底 + 深字（新增 `*-soft-solid/-soft-fg` 令牌），
  消息新到闪动改用 `primary-hover` 保证明暗两套可读

## v1.0.0 — 2026-08-16

50 版自主迭代（v21–v70）正式发布：前端体验优化 10 版、业务新功能 10 版、已有业务完善
10 版、逻辑闭环 10 版、收口 10 版。累计 283 项测试、ruff/mypy 全绿。完整交付明细如下。

### 功能

- 可观测性收口（v64）：请求耗时 ≥500ms 记结构化 `slow_request` 日志（方法/路径/毫秒）；
  `/healthz` 扩展数据库探测与版本（数据库异常返回 `degraded` 并记日志，不泄露细节）
- 前端渲染性能（v63）：消息列表超过 40 条改为 requestAnimationFrame 分块渲染（避免一次
  innerHTML 长阻塞，渲染完滚动到底）；图片消息预留最小宽高占位，懒加载时布局不跳动
- 会话摘要查询优化（v62）：单聊/群聊摘要改为「每会话 max(id) + 按 id 回取最后一条 +
  聚合 COUNT 未读」，不再整表拉取全部历史后内存计数；群成员数合并为一次 GROUP BY，消除
  N+1；行为与返回结构不变（278 项回归全绿）
- 无障碍收口（v61）：弹层打开自动聚焦首个可交互元素、Tab/Shift+Tab 焦点陷阱、关闭后焦点
  还原触发元素（MutationObserver 统一接管）；保留 aria-modal/role=dialog 与屏幕阅读器语义
- 端到端场景回归（v60）：`tests/test_e2e_flow.py` 用真实 WS 连接跑通「申请附言→接受→
  单聊→已读→建群→@提及→投票→禁言→解散」全链路，逐帧断言 friend/message/read_receipt/
  group_event/poll_event/notification 广播与 403/404 边界
- 群事件 UI 收敛（v59）：收到被移除/退出事件（含其他设备操作）立即收敛面板并提示
  「你已不在该群聊中」；角色变更提示新角色并刷新；解散/移出/退群后侧栏同步移除
- 多标签页协同（v57）：`storage` 事件联动——任一标签退出登录/会话失效，其他标签自动回登录页；
  任一标签重新登录，其他标签自动刷新；主题切换跨标签同步
- 输入校验前后端对齐（v56）：composer 剩余字数实时提示（接近上限显示，超限变红）；粘贴
  超长内容自动截断并提示「已按 2000 字上限截断」，与后端 strip/长度校验口径一致
- 相对时间显示（v55）：会话列表摘要显示「刚刚/x 分钟前/x 小时前/昨天/日期」，hover 显示
  完整时间（title 属性）；单聊/群聊/归档列表统一
- 空态/错误态全覆盖（v54）：侧栏首次加载失败显示「点击重试」入口；空会话显示「还没有消息，
  打个招呼吧」；搜索无结果显示「没有找到相关内容」；列表加载骨架与空态分流
- 免打扰未读徽标（v52）：免打扰会话改为灰色未读徽标（仍累计计数、仍计入标题角标），
  区分「静音但有事」与「无未读」
- 重连增量补拉（v51）：WS 重连成功后对活动会话拉取最新一页，与本地消息按 id 合并
  （补齐断线期间漏收消息、覆盖期间被编辑/撤回的旧载荷），不再整页重置历史
- 帮助与关于（v50）：`/api/version` 增 `app_version`；个人菜单「关于」弹窗展示应用/前端版本、
  品牌口号与快捷键提示
- 我的数据导出（v49）：`GET /api/me/export` 打包 JSON 附件（资料/好友/群/单聊与群消息
  （仅自己可见范围，每会话上限 20×100 条）/收藏，`Content-Disposition` 下载）；个人菜单
  「导出数据」一键下载
- 输入框表情面板（v48）：单聊/群聊 composer 新增 😊 按钮，弹出分类表情面板（常用/手势/
  符号），点击插入光标处并保留焦点与草稿；Esc 关闭
- 上传失败重试与提示（v47）：上传失败（类型/大小/网络）区分提示，进度浮层转红并提供
  「重试」按钮（保留原文件，取消则丢弃重试态）；批量上传中失败文件保留重试入口
- 群公告时间与空态（v46）：`groups.announcement_updated_at`（发布/清空即刷新），群详情
  公告横幅显示「发布于」时间；无公告时显示引导文案与空态样式
- 高风险操作二次确认（v45）：统一 `confirmModal` 覆盖退出登录、退出群聊、移除成员、撤回消息、
  删除好友（聊天头部新增删除入口，解除关系但保留记录）；确认文案明确后果
- 消息仅自己删除（v44）：`user_message_deletes` 表与 `DELETE .../messages/{id}/me`
  （单聊/群聊，幂等、校验归属）；删除后自己视角的历史/摘要/未读计数不再出现，对方与
  其他群成员视角不变；前端消息操作「删除」+ 统一确认弹窗
- 会话归档（v43）：`user_conversation_settings.archived`；`PATCH /api/conversations/settings`
  支持归档、`GET /api/conversations?archived=true|false` 过滤（缺省未归档）；前端会话行
  「归档」按钮与侧栏「已归档」分区（取消归档/直接打开）
- 发送状态与失败重试（v42）：消息先以本地乐观对象上屏（发送中转圈、半透明），成功后替换为
  服务端消息（WS 同步），失败标红并提供「重试」按钮；单聊/群聊发送均覆盖，本地消息不参与
  编辑/撤回/转发
- 会话草稿（v41）：按会话（单聊/群聊）自动把未发送内容存 localStorage（300ms 防抖），
  重新打开会话时恢复；发送成功即清除，切换会话互不干扰
- 好友申请附言（v40）：`friendships.reason`（≤200，strip 后空串存空）；申请/收发申请列表
  附 `reason`；前端「添加好友」改为弹层输入附言（发送前校验长度），申请卡片展示附言
- 通知中心（v39）：`notifications` 表与 `/api/me/notifications`（倒序游标 + 未读计数）、
  `POST /api/me/notifications/read`；事件源覆盖好友申请、@提及（单聊/群聊）、禁言/解除、
  角色变更、群解散，产生时 WS `notification` 定向推送；前端头部铃铛 + 未读角标 + 通知列表
  （点击跳转会话/群并定位消息，「全部已读」）
- 群已读明细（v38）：`GET /api/groups/{id}/messages/{mid}/reads`（仅成员、消息属该群且未
  撤回），自己的群消息载荷附 `read_count`；前端气泡「N 人已读」点击弹名单（头像 + 昵称 +
  已读/总数），WS 群已读回执实时推进计数（按人幂等去重，重载后以服务端为准）
- 群投票（v37）：`polls`/`poll_votes` 表与 `content_type:"poll"` 消息（问题 ≤120、2–10 个
  选项各 ≤60、可多选、不可带附件/引用/转发）；`PUT /api/groups/{id}/polls/{pid}/vote`
  投票/改票、`POST .../close` 结束（创建者或 owner/admin）、已关闭 409、非法下标 422；
  WS `poll_event(voted/closed)` 群内广播；前端群 composer「📊」发起弹窗、投票卡片（选项
  百分比条/已选高亮/参与数/结束投票按钮）
- 消息多选批量转发（v36）：聊天头部「多选」进入选择模式，消息左侧出现勾选框，底部操作条
  显示已选数量，可批量转发到好友/群（逐条调用既有转发接口，成功计数提示）；切换会话/取消
  自动退出选择态
- 群文件面板（v35）：`GET /api/groups/{id}/files` 聚合群内文件/语音附件（仅成员、倒序游标
  ≤50、排除已撤回）；前端群详情新增「文件」区（图标/文件名/大小/日期 + 加载更多），点击下载
- 语音消息（v34）：上传白名单增 `audio/webm`（EBML 魔数）与 `audio/mp4`（ftyp 魔数），
  消息 `content_type` 增 `audio`；前端麦克风按钮录音（MediaRecorder、时长计时、停止即上传
  发送），语音气泡 `<audio controls>` 播放；伪造类型仍 415
- 群解散（v33）：`POST /api/groups/{id}/dissolve`（仅 owner，admin/member 403）；显式清理
  群消息/回应/提及/收藏/成员/已读游标/会话设置（不依赖数据库级联，兼容哨兵占位设计）；
  WS `group_event(dissolved)` 广播全体；前端群主「解散群聊」入口 + 统一确认弹窗
  `confirmModal`（后续高风险操作复用），成员侧自动收敛面板并提示
- 群成员禁言（v32）：`group_members.muted`，`PATCH /api/groups/{id}/members/{sub}/mute`
  （owner/admin；不得禁言 owner/admin 与自己）；被禁言成员发群消息 403 `you are muted`，
  WS `group_event(member_muted)` 全成员广播；前端成员行禁言开关、被禁言者输入框/附件/提及
  按钮禁用并提示「你已被禁言」
- 好友备注名（v31）：`friendships.remark`（≤32、空串清除、仅本人可见），
  `PATCH /api/friends/{sub}/remark`；好友列表回传 remark，前端展示优先备注名，聊天头部新增
  「设置备注」入口（保存后立即刷新头部与列表）
- 键盘快捷键与帮助（v30）：Ctrl/Cmd+K 聚焦搜索、Ctrl/Cmd+Enter 发送、Esc 逐层关闭弹层/
  查看器/菜单/编辑态、`?` 打开快捷键帮助弹窗；个人菜单新增「快捷键」入口
- 标题未读角标与桌面通知（v29）：页面标题实时显示未读总数 `(n) Li&Chat`；页面后台时按偏好
  发桌面通知（个人菜单「通知设置」开关，首次开启申请授权，localStorage 记忆）
- 会话筛选与骨架屏（v28）：侧栏新增「筛选会话」输入，按名称/摘要实时过滤好友与群；
  首次加载列表显示 shimmer 骨架屏；修复会话列表含群摘要时 `peer.sub` 取值导致渲染中断的
  隐患（群/单聊摘要正确分流）
- 搜索命中定位与高亮（v27）：点击消息搜索命中后打开会话，自动向后翻历史直到找到该消息并
  滚动居中、闪烁高亮（最多翻 20 页防滥用），消息节点携带 data-message-id 供定位
- 上传进度条（v26）：附件上传改用 XHR 上报进度，底部浮层显示文件名/百分比进度条与取消按钮，
  401 仍统一跳登录，失败走友好错误提示（v21 的映射复用）
- 上传入口增强（v25）：输入框支持粘贴图片直接发送、文件拖拽到输入区上传、附件按钮多选批量
  发送（逐个上传并汇总成功提示），拖入时输入区显示虚线高亮
- 图片查看器（v24）：点击消息内图片打开全屏深色查看层，支持点击遮罩/关闭按钮/Esc 关闭，
  原图等比缩放展示，移动端安全区适配
- 消息阅读体验（v23）：聊天记录按天插入日期分隔线（今天/昨天/M月D日/跨年含年份）；
  群聊消息显示发送者头像与昵称，同一发送者 5 分钟内连续消息合并展示（头像/昵称只留首条），
  提升长会话扫读效率
- WebSocket 自动重连（v22）：非登出断线按 1s/2s/4s…上限 30s 指数退避重连，重连成功提示
  「已重新连接」并刷新会话列表、重拉活动会话历史补消息；页面恢复可见时立即重连；4401 与
  主动登出仍按原约定跳登录/停止
- 全局 Toast 与错误反馈（v21）：`toast()` 轻提示系统（info/success/error、aria-live、
  自动消退）；`api()` 统一解析错误 detail 并映射为友好中文提示（常见后端错误码对照表），
  网络失败/5xx 给出可操作提示；移除 `window.alert`；资料保存、头像更新、加好友、置顶/
  免打扰、群管理、收藏、转发等关键操作增加成功反馈
- 呼叫记录与未接来电：`call_logs` 落账（离线/忙线记 missed、拒接 rejected、接通 accepted、
  响铃中被挂断记 missed），`GET /api/me/calls` 倒序列表（附对端资料、kind/status/时间）；
  WS `call` 协议增加 `kind`（audio/video）；前端「通话记录」
- 会话管理：WS 连接级 session_id 跟踪、`GET /api/me/sessions`（含 `current` 标记）、
  `DELETE /api/me/sessions/{id}` 撤销单个会话并断其 WS（4401）、`DELETE /api/me/sessions`
  退出其他设备（保留当前）；前端「登录设备」列表与撤销按钮
- 群消息操作补齐：群内编辑/撤回（`PATCH/DELETE /api/groups/{id}/messages/{mid}`，发送者、
  5 分钟窗、墓碑；非成员 404）与表情回应（成员校验、幂等 toggle）；WS
  `message_edited/message_deleted/message_reaction` 群内广播；前端群消息启用编辑/撤回/表情
- 群公告与群头像：`groups.announcement`（≤2000，owner/admin 维护、可清空）、
  `groups.avatar_url`（owner/admin 引用本人上传的图片，非图片 422 / 他人附件 403）；WS
  `announcement_updated/avatar_updated` 全成员广播；前端群公告横幅/编辑与头像上传
- 会话置顶与免打扰：`user_conversation_settings`（dm/group 键归属校验：单聊必须包含本人、
  群必须为成员）、`PATCH /api/conversations/settings` upsert、会话摘要附 `pinned/muted`
  且置顶会话排在前面；前端会话行置顶/免打扰开关，免打扰会话不显示未读徽标
- 收藏消息：`user_stars` 幂等 star/unstar（`PUT/DELETE /api/messages/{id}/star`，仅自己
  可见范围、越权 404）、收藏列表 `GET /api/me/stars`（会话引用 + 倒序游标 ≤50）、历史载荷
  按查看者附 `starred`；前端收藏切换与「我的收藏」列表
- @提及：`message_mentions` 表与成员/对端校验（单聊仅对方、群仅成员，≤50 去重，非法 422）、
  载荷与 WS 事件附 `mentions`；前端群 composer「@」成员选择器与「@我」高亮
- 消息转发：`POST /api/conversations/{sub}/forward` 与 `/api/groups/{id}/forward`（源消息
  须在转发者可见范围、已撤回 409；DM↔群互转），复制文本/附件元数据并置 `forwarded` 标记；
  前端「转发」按钮与目标选择弹层
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

- 文档全量同步（v67）：README 功能清单/测试数（282）/项目结构/路线图对齐 v21–v70；
  architecture 表结构与模块清单同步；新增 docs/user-guide.md 用户指南；429 状态码口径扩展
- 部署收口（v66）：compose 透传写操作限流/上传上限并注释生产开关（prod/https/PostgreSQL）；
  部署指南新增 PostgreSQL 兼容性验证（驱动/建表/语义差异/多副本前提）
- 新增 design-system/chat/BRAND.md、MASTER.md 与 preview 视觉基线
- 新增 docs/superpowers UI 重构设计规格与实施计划
- 补齐 .env.example 全部配置项：LICHAT_*、compose 插值变量与镜像加速源（`BASE_IMAGE_REGISTRY` 与 `IMAGE_REGISTRY` 拆分，避免加速前缀污染应用镜像名）
- 新增 OIDC 对接文档：门户接口契约与实现逐项对照、应用注册地址、§2.4 验收清单、上线注意事项与联调步骤
- OIDC 配置口径固化：明确标准登记值（回程登出地址 `/oidc/backchannel-logout`、登出回跳白名单 `/`），`/oidc/post-logout` 的 `logout_token` 分支标注为旧门户行为兼容兜底

### 运维工具

- Docker 构建提速：Dockerfile 把 pip/uv/apt 缓存挂载为 BuildKit cache，移除 `uv sync
  --no-cache`——`pyproject.toml`/`uv.lock` 未变时依赖层秒级复用，锁文件变更时只下载增量
  wheel；不用 `# syntax` 指令（避免去 Docker Hub 拉前端镜像卡住）；部署指南补充镜像源切换
  与 BuildKit 说明
- 容器化部署：Dockerfile（python:3.12-slim + uv、非 root、构建期导入冒烟）与 docker-compose.yaml（单服务、命名卷持久化 SQLite、healthcheck、127.0.0.1 端口绑定）
- compose 新增编排内 redis（7-alpine、AOF、maxmemory 192mb、健康检查、口令可覆盖），chat 默认连接，支持外部 Redis 覆盖

### 行为变更

- 设计系统审计（v68）：回复引用条改为 `color-mix` 派生语义色（明暗主题一致，替换硬编码
  半透明黑）；MASTER.md 补录 v21–v70 新增组件清单并明确「新组件复用品牌令牌」约束
- 聊天输入占位提示改为「输入消息」，编辑态简化为「正在编辑，Enter 保存」；占位符单行
  `nowrap + overflow:hidden`，窄屏不再换行截断
- 移动端页面硬锁：`body` 固定定位 + 壳层 `touch-action:none`，从根上禁止整页拖动与 iOS
  橡皮筋回弹；输入框改为自动增高（单行起步、随内容增长、上限 120px 后内部滚动），发送/
  取消编辑/切会话后复位
- 前端版本检测与强制刷新：`GET /api/version` 下发前端版本，启动时与服务端比对，版本落后则
  清空 Cache Storage 并强制 `location.reload()`（sessionStorage 防刷新循环）；紧凑密度层
  明确仅桌面端（≥768px）生效，移动端保持 44px 触控热区
- 移动端进入聊天时保留个人状态顶栏，聊天框全出血占满其下剩余全屏（面板顶=顶栏底、输入框
  贴视口底），页面不可滚动、仅组件内滚动
- 页面滚动彻底锁定：`html/body` 均 `overflow:hidden` + `overscroll-behavior:none`，聊天页
  任何位置滚动都不会带动页面；消息列表/侧栏/弹层等内滚容器加 `overscroll-behavior:contain`
  与 `touch-action:pan-y`，防滚动穿透与移动端橡皮筋回弹
- 紧凑密度层：桌面端整体收紧组件尺寸（按钮 36px、图标钮 34px、头像 30px、气泡 0.92rem、
  更细的列表/气泡/弹层间距），消除「老人感」；移动端保留 ≥44px 触控热区与更宽松的消息
  排版，可用性不降级
- 登录后界面改为微信式全高双栏布局（保留品牌令牌）：页面不再滚动，会话列表与聊天面板
  各自内滚；桌面整体限位 1200px、消息/输入内容列限位 880px；移动端单栏切换（列表 ↔ 聊天）、
  顶栏/输入框适配安全区、隐藏页脚
- 附件回源授权从「仅上传者」放宽为「上传者或引用该附件的会话参与者」：修复收件人无法
  查看图片/下载文件的缺陷；陌生人仍 403
- SSO 资料同步改为「昵称/头像仅空值回填」：本地编辑的个人资料不再被门户 userinfo 覆盖
  （`name`/`email` 仍随登录同步）
- SQLite 连接启用 `journal_mode=WAL` 与 `busy_timeout=5000`：缓解读写并发互锁与瞬时
  锁竞争（生产同样受益；PostgreSQL 不受影响）
- OIDC 授权 scope 默认加入 `email`：登录时向 Li&Pass 请求邮箱并同步到本地资料，支撑「按邮箱搜索好友」；未验证邮箱不阻塞登录（仅存储 `email_verified` 标记），授权同意页可能多一项邮箱授权
- RP 登出携带 `id_token_hint`：登录时把 `id_token` 存进本地会话（仅作登出提示），网站内退出登录跳门户 `end-session` 时随 `client_id` 一起携带，门户据此展示「退出所有会话 / 仅退出当前网站」确认页，而不是打回授权确认
- 移除 `/oidc/post-logout` 的兼容逻辑：该端点恢复标准形态（仅 GET 带签名 `state` 回跳，验签后 302 首页），POST/`logout_token` 一律 405；回程登出统一走 `/oidc/backchannel-logout`

### 安全加固

- 写操作限流（v65）：发消息/编辑/上传/投票按用户滑动窗口限流（`LICHAT_ACTION_RATE_LIMIT`
  默认 60/60 秒），超限 429 + Retry-After；进程内实现，多副本仍需共享存储
- 登录限流：`/oidc/login` 与 `/oidc/callback` 按客户端 IP 做进程内滑动窗口限流
  （`LICHAT_LOGIN_RATE_LIMIT` 默认 10、`LICHAT_LOGIN_RATE_WINDOW` 默认 60 秒），超限
  429 + `Retry-After`；多副本部署仍需网关或共享存储限流
- 授权单飞：同一浏览器重复发起登录时复用未完成的 auth state（`lichat_auth` HttpOnly Cookie），授权完成后即删除状态并清 Cookie——其他仍在等待的授权确认页随之作废，不再并行放行出多个会话
- 会话守护加强：RP 登出即断开该用户全部 WebSocket（配置 Redis 时跨副本广播），登出标签页不再继续收到实时消息；WS 心跳每次重新校验会话，会话被删除/过期立即以 4401 关闭

### 缺陷修复

- 移动端兼容细节（v69）：iOS 输入字号统一 16px 防聚焦自动放大；交互元素去除点击高亮灰闪；
  弹层底部补安全区留白；100dvh 保留 100vh 回退（此前已有）
- 请求竞态防护（v58）：会话切换时递增 epoch，历史/群文件/已读回执等异步响应返回后校验
  epoch，过期响应直接丢弃，防止快速切换会话时旧数据覆盖新会话
- 已读回执一致性（v53）：退群/被移除时显式清理该用户的群已读游标与群会话设置（此前外键
  级联未生效会残留孤儿行）；补充 DM 游标只前进的回归测试
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
