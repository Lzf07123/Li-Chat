# 接口文档

## REST

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/healthz` | 无 | 健康检查，返回 `{"status":"ok"}` |
| GET | `/api/version` | 无 | 前端版本 `{"frontend_version":"0.3.0"}`（`no-store`；前端据此检测落后并强制刷新） |
| GET | `/oidc/login?redirect_after=/` | 无 | 生成 PKCE 并 302 到授权页；`redirect_after` 仅接受站内相对路径 |
| GET | `/oidc/callback` | 无 | 授权回调（code/state/error/error_description），成功 302 回 `redirect_after` 并种会话 Cookie |
| GET | `/oidc/error?message=` | 无 | 登录错误页，返回 `{"message": ...}` |
| POST | `/oidc/logout` | CSRF | 清本地会话，302 到 IdP `end-session` |
| GET | `/oidc/post-logout?state=` | 无 | 门户登出回跳（浏览器 GET 带签名 `state`）：验签后 302 首页，无效 400 |
| POST | `/oidc/backchannel-logout` | 无 | 门户服务器间调用，form 字段 `logout_token`，返回 `{"status":"ok"}` 或 `{"status":"ignored"}` |
| GET | `/api/me` | 会话 | 当前用户 `{sub, nickname, name, picture, email, csrf_token}` |
| PATCH | `/api/me` | 会话 + CSRF | 改资料 `{"nickname"?, "bio"?}`（昵称 1–32、简介 ≤200） |
| POST | `/api/me/avatar` | 会话 + CSRF | 设头像 `{"url"}`（须为本人上传的图片）；422 非图片/非法地址、403 他人附件 |
| PUT | `/api/messages/{id}/star` | 会话 + CSRF | 收藏（幂等；仅自己可见范围，越权 404）；`{"message_id","starred":true}` |
| DELETE | `/api/messages/{id}/star` | 会话 + CSRF | 取消收藏（幂等）；`{"message_id","starred":false}` |
| GET | `/api/me/stars?cursor=&limit=` | 会话 | 收藏列表（倒序游标 ≤50；附会话引用与内容摘要）；`{"messages":[...],"next_before"}` |
| GET | `/api/me/sessions` | 会话 | 当前用户的登录会话列表（含 `current` 标记）；`{"sessions":[{id,created_at,last_seen_at,expires_at,current}]}` |
| DELETE | `/api/me/sessions/{id}` | 会话 + CSRF | 撤销我的某个会话并断其 WS（4401）；越权 404 |
| DELETE | `/api/me/sessions` | 会话 + CSRF | 撤销除当前外全部会话（退出其他设备） |
| GET | `/api/me/calls?cursor=&limit=` | 会话 | 通话记录（倒序游标 ≤50，附对端资料）；`{"calls":[{id,kind,status,started_at,ended_at,peer}],"next_before"}` |
| GET | `/api/me/notifications?cursor=&limit=` | 会话 | 站内通知（倒序游标 ≤50）；`{"notifications":[{id,type,actor,group,payload,read,created_at}],"next_cursor","unread_count"}` |
| POST | `/api/me/notifications/read` | 会话 + CSRF | 全部通知标记已读；`{"status":"ok"}` |
| GET | `/api/users/search?q=` | 会话 | 昵称/邮箱关键词搜索（1–64 字符，≤20 条）；返回 `sub/nickname/name/picture/friend_status`，不回传邮箱 |
| GET | `/api/search?kind=messages&q=&limit=&before=` | 会话 | 消息全文搜索（仅自己可见范围：单聊双方/群成员；LIKE 不区分大小写、倒序游标、命中片段）；`{"messages":[{id,sender_sub,conversation:{type,peer_sub,peer_name,group_id,group_name},snippet,created_at}],"next_before"}` |
| GET | `/api/search?kind=contacts&q=` | 会话 | 联系人搜索（语义同 `/api/users/search`）；`{"contacts":[{sub,nickname,name,picture,friend_status}]}` |
| GET | `/api/friends` | 会话 | 已接受好友列表 `{"friends":[{...Profile,bio,online:bool,last_seen_at:str|null}]}`（bio 仅好友可见） |
| PATCH | `/api/friends/{sub}/remark` | 会话 + CSRF | 设置/清除好友备注名 `{"remark"}`（≤32，空串清除，仅好友关系内）；`{"remark":...}` |
| GET | `/api/friends/requests` | 会话 | `{"incoming":[{"requester":Profile,"created_at"}],"outgoing":[{"addressee":Profile,"created_at"}]}` |
| GET | `/api/friends/recommendations?limit=` | 会话 | 随机推荐（默认 5、1–20）；排除自己、好友与双方待处理申请，返回 `{"friends":[Profile]}`，不回传邮箱 |
| POST | `/api/friends/requests` | 会话 + CSRF | 发申请 `{"to_sub":"...","message"?:≤200}`；201 返回申请对象（附 `reason`）；400 自加 / 404 未知 / 409 重复或已是好友 / 422 附言超长 |
| POST | `/api/friends/requests/{from_sub}/accept` | 会话 + CSRF | 仅被申请人可接受；`{"status":"accepted"}` |
| POST | `/api/friends/requests/{from_sub}/reject` | 会话 + CSRF | 仅被申请人可拒绝；`{"status":"rejected"}` |
| DELETE | `/api/friends/{sub}` | 会话 + CSRF | 解除与对方的任何关系（好友或撤回申请）；`{"status":"removed"}` |
| POST | `/api/groups` | 会话 + CSRF | 建群 `{"name"(1–64),"member_subs":[...]}`（≤20、须为创建者好友）；201 返回群详情 |
| GET | `/api/groups` | 会话 | 我加入的群列表 `{"groups":[Group]}`（按 id 倒序） |
| GET | `/api/groups/{id}` | 会话 | 群详情（仅成员可见）；Group = `{id,name,owner_sub,created_at,members:[{user,role,joined_at}]}` |
| PATCH | `/api/groups/{id}` | 会话 + CSRF | 改名（owner/admin）`{"name"}` |
| POST | `/api/groups/{id}/members` | 会话 + CSRF | 邀请（owner/admin；被邀者须为邀请人好友，≤20） |
| DELETE | `/api/groups/{id}/members/{sub}` | 会话 + CSRF | 移除（owner/admin；admin 不可移除 owner/admin，owner 可移除 admin） |
| PATCH | `/api/groups/{id}/members/{sub}` | 会话 + CSRF | 调整角色 `{"role":"admin|member"}`（仅 owner，不可改 owner 自身） |
| PATCH | `/api/groups/{id}/members/{sub}/mute` | 会话 + CSRF | 禁言/解除禁言 `{"muted":bool}`（owner/admin；不得禁言 owner/admin 与自己）；被禁言者发消息 403 |
| POST | `/api/groups/{id}/leave` | 会话 + CSRF | 退出（owner 须先转让，409） |
| POST | `/api/groups/{id}/dissolve` | 会话 + CSRF | 解散（仅 owner）；级联清理群消息/成员/已读/会话设置，WS `dissolved` 广播全体 |
| POST | `/api/groups/{id}/transfer` | 会话 + CSRF | 转让 `{"new_owner_sub"}`（仅 owner，目标须为成员） |
| PATCH | `/api/groups/{id}/announcement` | 会话 + CSRF | 公告 `{"text"}`（≤2000，可清空；owner/admin） |
| POST | `/api/groups/{id}/avatar` | 会话 + CSRF | 群头像 `{"url"}`（本人上传的图片；owner/admin） |
| POST | `/api/groups/{id}/messages` | 会话 + CSRF | 群发消息（文本/附件/语音/投票/引用/提及，语义同单聊；仅成员；mentions 须为群成员）；投票消息 `content_type:"poll"` + `poll:{question,options,multiple}`（问题 ≤120、2–10 个选项各 ≤60，不可带附件/引用）；201 返回消息（附 `group_id`/`poll`）；WS 推全成员 |
| GET | `/api/groups/{id}/messages?limit=&before=` | 会话 | 群历史倒序分页（仅成员；参数语义同单聊） |
| GET | `/api/groups/{id}/messages/{mid}/reads` | 会话 | 群消息已读明细（仅成员、消息须属该群且未撤回）；`{"read_count","total_members","readers":[{sub,nickname,name,picture}]}`；自己的群消息载荷附 `read_count` |
| GET | `/api/groups/{id}/files?limit=&before=` | 会话 | 群内文件/语音附件聚合（仅成员，倒序游标 ≤50）；`{"files":[{message_id,sender_sub,name,size,mime,url,created_at}],"next_before"}` |
| PUT | `/api/groups/{id}/polls/{pid}/vote` | 会话 + CSRF | 投票/改票 `{"option_indexes":[...]}`（仅成员；单选投票最多 1 项；已关闭 409；非法下标 422）；WS `poll_event(voted)` 群内广播 |
| POST | `/api/groups/{id}/polls/{pid}/close` | 会话 + CSRF | 结束投票（创建者或 owner/admin）；WS `poll_event(closed)` 群内广播 |
| PATCH | `/api/groups/{id}/messages/{mid}` | 会话 + CSRF | 群消息编辑（发送者、未撤回、5 分钟内；非成员 404 / 非发送者 403） |
| DELETE | `/api/groups/{id}/messages/{mid}` | 会话 + CSRF | 群消息撤回（同上鉴权；墓碑不含原文） |
| PUT | `/api/groups/{id}/messages/{mid}/reactions` | 会话 + CSRF | 群消息回应（仅成员，幂等） |
| DELETE | `/api/groups/{id}/messages/{mid}/reactions?emoji=` | 会话 + CSRF | 群消息移除回应（仅成员，幂等） |
| POST | `/api/groups/{id}/read` | 会话 + CSRF | 群已读 `{"last_read_id"}`（仅成员、消息须属该群、游标只前进）；WS 推全成员 |
| POST | `/api/groups/{id}/forward` | 会话 + CSRF | 转发到群 `{"message_id"}`（仅成员、源消息自己可见、未撤回）；`forwarded:true` |
| POST | `/api/uploads` | 会话 + CSRF | multipart `file`；大小 ≤ `LICHAT_UPLOAD_MAX_MB`、内容嗅探白名单（jpeg/png/gif/webp/pdf/txt/audio/webm/audio/mp4）；413 超限 / 415 非法类型；201 `{id,url,name,size,mime}` |
| GET | `/api/uploads/{filename}` | 会话 | 回源（上传者或引用该附件的会话参与者；图片 inline，其他 attachment；nosniff）；401 未登录 / 403 越权 / 404 不存在 |
| POST | `/api/conversations/{sub}/messages` | 会话 + CSRF | 发消息 `{"content","content_type":"text|image|file|audio","attachment":{url},"reply_to_id","mentions"}`；文本 1–2000 strip 校验，附件/语音消息可带 ≤2000 说明且附件必须属于发送者；reply_to_id 必须同会话（否则 404）；mentions 仅允许对方（否则 422）；201 返回完整消息；400 自聊 / 403 非好友 / 404 未知 |
| POST | `/api/conversations/{sub}/forward` | 会话 + CSRF | 转发 `{"message_id"}`（源消息须自己可见、未撤回；目标须好友）；`forwarded:true` |
| GET | `/api/conversations/{sub}/messages?limit=&before=` | 会话 | 历史倒序分页（limit 默认 50、1–100；before 为上一页最小 id 不含）；`{"messages":[...],"next_before":int|null}` |
| PATCH | `/api/conversations/{sub}/messages/{id}` | 会话 + CSRF | 编辑 `{"content"}`；仅发送者、未撤回、5 分钟内；403 非发送者 / 404 不存在 / 409 已撤回或超窗 |
| DELETE | `/api/conversations/{sub}/messages/{id}` | 会话 + CSRF | 撤回；同上鉴权；返回墓碑 `{id,sender_sub,recipient_sub,deleted:true,created_at}`（不含原文） |
| PUT | `/api/conversations/{sub}/messages/{id}/reactions` | 会话 + CSRF | 回应 `{"emoji"}`（1–8 字符，禁空白/控制符；幂等）；404 非参与者 / 409 已撤回；`{"message_id","emoji","action":"added","count"}` |
| DELETE | `/api/conversations/{sub}/messages/{id}/reactions?emoji=` | 会话 + CSRF | 移除回应（幂等）；`{"message_id","emoji","action":"removed","count"}` |
| GET | `/api/conversations` | 会话 | 单聊 + 群聊摘要合并，置顶优先、其余按最后消息倒序；每项 `{peer:Profile|null,group:{id,name,owner_sub,member_count}|null,last_message:Message|null,unread_count:int,last_read_id:int,pinned:bool,muted:bool}`（peer/group 二选一出现） |
| PATCH | `/api/conversations/settings` | 会话 + CSRF | 置顶/免打扰 `{"kind":"dm|group","key","pinned"?, "muted"?}`（至少一项；键须归属本人，否则 404）；返回 `{kind,key,pinned,muted}` |
| POST | `/api/conversations/{sub}/read` | 会话 + CSRF | 标记已读 `{"last_read_id":int>=1}`；403 非好友 / 404 消息不属于该会话；游标只前进；`{"status":"ok","last_read_id":n}` |
| GET | `/` | 无 | 同源前端页面 |

## WebSocket `/ws`

- 握手携带同源 Cookie，会话无效在 accept 后以 **4401** 关闭。
- 连接成功后服务端推送 `{"type":"hello","sub":"..."}`。
- 客户端发 `{"type":"ping"}` 收到 `{"type":"pong"}`，前端每 25 秒心跳一次。
- 客户端可发 `{"type":"typing","to":"<sub>","action":"start|stop"}`：仅双方为好友且满足
  2 秒限频时，服务端原样中继为 `{"type":"typing","from":"<sub>","action":...}`；否则静默丢弃。
- 客户端可发 `{"type":"call","op":"offer|answer|ice|reject|end","to":"<sub>","kind":"audio|video","payload":{}}`：
  仅好友间中继为 `{"type":"call","op":...,"from":"<sub>","payload":...}`；载荷 ≤16KB、ICE
  限频；离线回 `unavailable`、通话中重复 offer 回 `busy`、非法迁移回 `invalid`、超限回
  `error`（只回发起方）。媒体走 WebRTC P2P，服务端不中转流、不落信令。
- 回程登出会主动以 4401 断开该用户连接，前端据此跳转登录。
- 服务端推送（只增不改，客户端写操作一律走 REST）：`{"type":"message","message":{id,sender_sub,recipient_sub,content,created_at,edited_at?}}` → 发送方与接收方；`{"type":"message_edited","message":...}` / `{"type":"message_deleted","message":{...,deleted:true}}` → 双方（撤回墓碑不含原文）；`{"type":"message_reaction","message_id","emoji","action":"added|removed","count","by_sub"}` → 双方；`{"type":"read_receipt","by_sub","peer_sub","last_read_id"}` → 会话另一方；`{"type":"presence","sub","online":true}` / `{"type":"presence","sub","online":false,"last_seen_at"}` → 该用户全部好友（上线/全部连接释放时）；`{"type":"group_event","event":"created|renamed|member_joined|member_removed|member_left|role_changed|owner_changed","group":Group,"by_sub":...,"at":...}` → 群全体成员；`{"type":"call","op":...,"from":...,"payload":...}` → 呼叫对端；`{"type":"friend_event","event":"request_received|request_accepted|request_rejected|friend_removed","by_sub":...,"at":...}` → 相关方（申请→被申请人；接受/拒绝→申请人；解除→关系另一方）。

## CSRF 约定

对非安全方法（如 `POST /oidc/logout`）二选一携带：请求头 `X-CSRF-Token: <csrf_token>`，或表单字段 `csrf_token`。令牌从 `/api/me` 获取。

## 状态码约定

| 状态码 | 含义 |
| --- | --- |
| 400 | 回调 state 无效/重放、logout state 或 logout_token 校验失败 |
| 401 | 未登录、会话过期、id_token 校验失败、userinfo sub 不一致 |
| 403 | CSRF 校验失败 |
| 409 | 好友/申请冲突（已申请、已是好友、对方已申请） |
| 429 | 登录限流（`/oidc/login`、`/oidc/callback` 超窗口配额，附 `Retry-After`） |
| 422 | 参数校验失败（搜索串、消息内容、分页参数越界） |
| 502 | IdP 响应缺令牌、userinfo 请求失败 |
| 302 | 登录/登出跳转 |

## 会话 Cookie

名称 `lichat_session`，属性 `HttpOnly + SameSite=Lax + Path=/`，生产加 `Secure`，最大存活 7 天（滑动 2 小时）。
