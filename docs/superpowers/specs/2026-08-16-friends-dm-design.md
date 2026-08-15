# Li&Chat 好友与单聊设计规格（里程碑二）

- 状态：已确认（产品决策与整体方案经用户逐项确认，2026-08-16）
- 日期：2026-08-16
- 前置：里程碑一（OIDC 单点登录）已交付

## 1. 目标与范围

在现有身份体系之上实现小圈子的好友关系与一对一实时纯文本聊天：

- 用户可按昵称/邮箱关键词搜索他人并发起好友申请
- 申请-同意制：被申请人接受后双方互为好友，拒绝后申请消失
- 任一好友可解除关系（含撤回待处理申请）；解除后历史消息双方仍可见
- 好友之间互发纯文本消息：落库 + 实时双向推送 + 上线/打开会话拉取历史

不包括（见 §11）：未读/已读、离线推送、群聊、图片/文件消息、拉黑、消息撤回/编辑。

## 2. 已确认的产品决策

| 决策点 | 结论 |
| --- | --- |
| 好友模型 | 申请-同意制，接受后双向等同 |
| 查找方式 | 按昵称/邮箱关键词搜索（`LIKE` 子串，不含邮箱回传） |
| 消息类型 | 纯文本，1–2000 字符 |
| 解除关系 | 任一方删除即解除；历史双方保留 |
| 离线消息 | 持久化 + 上线/打开会话拉取历史；无未读徽标 |
| 整体方案 | REST 落库 + WS 实时推送（方案 A） |

## 3. 数据模型

不动现有 `users/auth_states/sessions` 三表；新增两张表，由 lifespan `create_all` 建表（当前无 Alembic）。

### 3.1 friendships

| 列 | 类型 | 说明 |
| --- | --- | --- |
| requester_sub | String(64) PK, FK users.sub | 申请人 |
| addressee_sub | String(64) PK, FK users.sub | 被申请人 |
| status | String(16) | `pending` / `accepted` |
| created_at / updated_at | DateTime | 默认 utcnow，updated_at 更新时刷新 |

约束：`requester_sub != addressee_sub`；复合主键保证同一对用户最多一条关系；申请方向由 requester 表达，`accepted` 后双向等同。

### 3.2 messages

| 列 | 类型 | 说明 |
| --- | --- | --- |
| id | BigInteger PK autoincrement（SQLite INTEGER / PostgreSQL BIGINT，`with_variant`） | 全局单调，兼作历史游标 |
| sender_sub / recipient_sub | String(64), FK users.sub | 发送方/接收方 |
| participant_lo / participant_hi | String(64) | 双方 sub 字典序（lo < hi） |
| content | Text | 纯文本 |
| created_at | DateTime | 默认 utcnow |

约束：`sender_sub != recipient_sub`、`participant_lo < participant_hi`；索引 `(participant_lo, participant_hi, id)` 支撑「两人历史」单索引查询，SQLite 与 PostgreSQL 语义一致。

## 4. REST 接口契约

除 `/oidc/*` 与 `/healthz` 外全部会话鉴权（401 语义同 `/api/me`）；写操作（POST/DELETE）校验 CSRF（403）。用户资料回传统一为 `{sub, nickname, name, picture}`，不回传邮箱。

| 方法/路径 | 请求 | 成功响应 | 错误 |
| --- | --- | --- | --- |
| GET `/api/users/search?q=` | `q` 1–64 字符 | `{"results":[Profile & friend_status]}` | 422 |
| GET `/api/friends` | — | `{"friends":[Profile]}` | — |
| GET `/api/friends/requests` | — | `{"incoming":[{"requester":Profile,"created_at"}], "outgoing":[{"addressee":Profile,"created_at"}]}` | — |
| POST `/api/friends/requests` | `{"to_sub":"..."}` | 201 `{"requester_sub","addressee_sub","status":"pending","created_at"}` | 400 自加 / 404 未知用户 / 409 重复或已是好友 |
| POST `/api/friends/requests/{from_sub}/accept` | — | `{"status":"accepted"}` | 404 无此申请 |
| POST `/api/friends/requests/{from_sub}/reject` | — | `{"status":"rejected"}` | 404 无此申请 |
| DELETE `/api/friends/{sub}` | — | `{"status":"removed"}` | 404 无关系 |
| POST `/api/conversations/{sub}/messages` | `{"content":"..."}` | 201 `Message`（完整消息对象） | 400 自聊 / 403 非好友 / 404 未知用户 / 422 空或超长 |
| GET `/api/conversations/{sub}/messages?limit=&before=` | `limit` 默认 50、1–100；`before` 为上一页最小 id（不含） | `{"messages":[Message 倒序], "next_before":int|null}` | 422 参数越界 |

- `friend_status`：`none` / `incoming`（对方已申请我）/ `outgoing`（我已申请对方）/ `friends`。
- `Message`：`{"id":int,"sender_sub":"...","recipient_sub":"...","content":"...","created_at":"ISO8601Z"}`。
- 时间一律 UTC 序列化，后缀 `Z`（naive UTC 存储，序列化时补 Z，避免前端按本地时区误解析）。
- 边界决策：
  - 双方互发申请：后发方 409「对方已向你发起申请，请先处理」；界面引导先处理申请。
  - 撤回已发出申请与解除好友共用 DELETE；删除后重新成为好友需重新申请。
  - 历史访问边界即「参与者」：会话键由 `(me, other)` 构成，任何已登录用户只能查自己参与的会话；陌生人会话返回空列表，无需额外鉴权分支。
  - 接受/拒绝仅被申请人可操作（`from_sub` 路径参数 + 会话身份双校验）。

## 5. WebSocket 协议（只增不改）

握手鉴权、4401 语义、ping/pong 心跳保持不变；客户端不新增入站命令（所有写操作走 REST）。新增服务端推送：

| 消息 | 目标 | 载荷 |
| --- | --- | --- |
| `{"type":"message","message":Message}` | 发送方与接收方（多标签页同步） | 完整 Message 对象 |
| `{"type":"friend_event","event":"request_received","by_sub":requester,"at":ISO8601Z}` | 被申请人 | 收到新申请 |
| `{"type":"friend_event","event":"request_accepted","by_sub":addressee,"at":...}` | 申请人 | 申请被接受 |
| `{"type":"friend_event","event":"request_rejected","by_sub":addressee,"at":...}` | 申请人 | 申请被拒绝 |
| `{"type":"friend_event","event":"friend_removed","by_sub":deleter,"at":...}` | 关系另一方 | 被解除/被撤回 |

前端收到 friend_event 后重新拉取 `/api/friends` 与 `/api/friends/requests`，不信任推送快照。

## 6. 安全与授权

| 要求 | 实现 |
| --- | --- |
| 搜索不泄露邮箱 | 匹配用邮箱，结果只回 sub/nickname/name/picture；结果限 20、查询限 64 |
| 写操作 CSRF | POST/DELETE 走 `require_csrf`（沿用双提交令牌） |
| 申请生命周期 | 接受/拒绝仅被申请人；解除仅关系一方；重复申请/自加被拒 |
| 发消息 | 双方必须 `accepted` 好友；内容 1–2000、strip 后校验；禁止自聊 |
| 读历史 | 会话键天然限定参与者，无跨用户读取路径 |
| XSS | 消息内容与昵称前端一律 `textContent`/`escapeHtml` 渲染，不拼 HTML |
| 日志 | 沿用结构化日志，不落消息内容 |

## 7. 前端设计

`static/app.js` 的 AppShell 改为双栏（沿用 BRAND/MASTER 令牌）：

- 左侧栏：用户搜索（`.input` 输入 + 提交）、好友申请区（incoming 接受/拒绝、outgoing 撤回，角标计数）、好友列表（点击打开会话）。
- 右侧聊天面板：会话头（头像/昵称/返回）、`role="log"` 消息区（自己消息靠右主色气泡，他人靠左表面气泡，时间后缀）、历史「加载更早」按钮（`next_before` 游标翻页）、输入框（textarea，Enter 发送 / Shift+Enter 换行，maxlength 2000）。
- 实时：WS `message` 到达且属于当前会话即追加（按 id 去重）；`friend_event` 触发重拉列表。
- 移动端（<768px）：列表与聊天两态切换，聊天面板带返回按钮。
- 无障碍：焦点可见、可点击 ≥44px、`sr-only` 标签、消息区 aria-live、reduced-motion 尊重既有约定。

文件：`static/app.js`（逻辑）、`static/style.css`（新增 `--chat-*` 语义组件类）；`brand.js` 不动。

## 8. 模块划分

| 文件 | 职责 |
| --- | --- |
| `app/models.py` | 新增 Friendship / Message |
| `app/friends/service.py` | 搜索、friend_status、申请生命周期、关系查询（业务与错误映射） |
| `app/api/friends.py` | `/api/friends/*` 薄路由（新增） |
| `app/api/users.py` | 增加 `GET /api/users/search` |
| `app/messages/service.py` | 发送、历史分页、长度/关系校验（新增） |
| `app/api/messages.py` | `/api/conversations/*` 薄路由（新增） |
| `app/main.py` | 注册两个新路由 |
| `app/timeutil.py` | 增加 `iso_utc`（naive UTC → ISO8601Z） |
| `app/ws/manager.py` | 不变，复用 `send_to` |

路由保持薄；业务与错误映射在 service；WS 推送由路由在落库成功后经 `request.app.state.ws_manager` 触发。

## 9. 测试策略

沿用 `httpx.ASGITransport` + 本地 IdP，零外网；用户/会话直接落库种子（参考 `tests/test_ws.py`），公共种子助手放 `tests/fixtures/chat.py`。

- `tests/test_models.py`：两张新表 roundtrip 与约束（自环插入被拒）。
- `tests/test_friends.py`：搜索（匹配、限长限数、排除自己、status 四态、不回传邮箱）；申请（成功/自加 400/未知 404/重复 409/互申 409）；列表与接受/拒绝/解除的权限矩阵（401/403/404/409/422）；解除后历史仍可读。
- `tests/test_messages.py`：发送（成功/非好友 403/自聊 400/空白超长 422/未知 404）；历史（倒序、游标翻页、`next_before` 终止、陌生人空列表、越界 422）。
- WS 端到端（并入 `tests/test_friends.py` / `tests/test_messages.py`）：TestClient 单客户端 WS——发消息双方实时收到；request_received/accepted/rejected/friend_removed 四类事件送达正确目标。
- 质量门禁：`uv run pytest -q` 全绿、`uv run ruff check .`、`uv run mypy app`。

## 10. 验收标准

- 双账号真机冒烟：搜索 → 申请 → 实时收到事件 → 接受 → 互发消息实时可见 → 刷新后历史仍在 → 一方删除 → 双方不能再发但历史可见 → 重新申请恢复。
- 62 个既有测试 + 新增测试全绿，ruff/mypy 全绿。
- 明暗主题、移动端两态、reduced-motion、键盘操作可用。

## 11. 非目标（后续里程碑）

未读/已读回执与离线推送（里程碑三）、群聊（里程碑三）、音视频（里程碑四）、图片/文件消息、拉黑、消息撤回/编辑、账号注销、发送频率限制。

## 12. 约束与风险

- 多副本：WS 推送与好友/消息落库均为单副本语义；多副本需共享数据库（PostgreSQL + Alembic，既有上线前事项），跨副本实时送达不在本次范围。
- SQLite 默认不强制外键（沿用现状，测试同样不依赖 FK 强制）。
- 登录接口无限流为既有遗留风险，消息发送限流不在本次范围。
