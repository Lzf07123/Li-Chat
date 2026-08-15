# 接口文档

## REST

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/healthz` | 无 | 健康检查，返回 `{"status":"ok"}` |
| GET | `/oidc/login?redirect_after=/` | 无 | 生成 PKCE 并 302 到授权页；`redirect_after` 仅接受站内相对路径 |
| GET | `/oidc/callback` | 无 | 授权回调（code/state/error/error_description），成功 302 回 `redirect_after` 并种会话 Cookie |
| GET | `/oidc/error?message=` | 无 | 登录错误页，返回 `{"message": ...}` |
| POST | `/oidc/logout` | CSRF | 清本地会话，302 到 IdP `end-session` |
| GET/POST | `/oidc/post-logout` | 无 | 门户登出回跳：带 `state` 时验签后 302 首页；带 `logout_token` 时按回程登出校验（kid/iss/aud/120s/jti/events）清 `(sub,sid)` 会话并断 WS，返回 `{"status":"ok"/"ignored"}`；否则 400 并记录来源与字段名 |
| POST | `/oidc/backchannel-logout` | 无 | 门户服务器间调用，form 字段 `logout_token`，返回 `{"status":"ok"}` 或 `{"status":"ignored"}` |
| GET | `/api/me` | 会话 | 当前用户 `{sub, nickname, name, picture, email, csrf_token}` |
| GET | `/api/users/search?q=` | 会话 | 昵称/邮箱关键词搜索（1–64 字符，≤20 条）；返回 `sub/nickname/name/picture/friend_status`，不回传邮箱 |
| GET | `/api/friends` | 会话 | 已接受好友列表 `{"friends":[Profile]}` |
| GET | `/api/friends/requests` | 会话 | `{"incoming":[{"requester":Profile,"created_at"}],"outgoing":[{"addressee":Profile,"created_at"}]}` |
| POST | `/api/friends/requests` | 会话 + CSRF | 发申请 `{"to_sub":"..."}`；201 返回申请对象；400 自加 / 404 未知 / 409 重复或已是好友 |
| POST | `/api/friends/requests/{from_sub}/accept` | 会话 + CSRF | 仅被申请人可接受；`{"status":"accepted"}` |
| POST | `/api/friends/requests/{from_sub}/reject` | 会话 + CSRF | 仅被申请人可拒绝；`{"status":"rejected"}` |
| DELETE | `/api/friends/{sub}` | 会话 + CSRF | 解除与对方的任何关系（好友或撤回申请）；`{"status":"removed"}` |
| POST | `/api/conversations/{sub}/messages` | 会话 + CSRF | 发纯文本 `{"content":"..."}`（1–2000，strip 校验）；201 返回完整消息；400 自聊 / 403 非好友 / 404 未知 |
| GET | `/api/conversations/{sub}/messages?limit=&before=` | 会话 | 历史倒序分页（limit 默认 50、1–100；before 为上一页最小 id 不含）；`{"messages":[...],"next_before":int|null}` |
| GET | `/` | 无 | 同源前端页面 |

## WebSocket `/ws`

- 握手携带同源 Cookie，会话无效在 accept 后以 **4401** 关闭。
- 连接成功后服务端推送 `{"type":"hello","sub":"..."}`。
- 客户端发 `{"type":"ping"}` 收到 `{"type":"pong"}`，前端每 25 秒心跳一次。
- 回程登出会主动以 4401 断开该用户连接，前端据此跳转登录。
- 服务端推送（只增不改，客户端写操作一律走 REST）：`{"type":"message","message":{id,sender_sub,recipient_sub,content,created_at}}` → 发送方与接收方；`{"type":"friend_event","event":"request_received|request_accepted|request_rejected|friend_removed","by_sub":...,"at":...}` → 相关方（申请→被申请人；接受/拒绝→申请人；解除→关系另一方）。

## CSRF 约定

对非安全方法（如 `POST /oidc/logout`）二选一携带：请求头 `X-CSRF-Token: <csrf_token>`，或表单字段 `csrf_token`。令牌从 `/api/me` 获取。

## 状态码约定

| 状态码 | 含义 |
| --- | --- |
| 400 | 回调 state 无效/重放、logout state 或 logout_token 校验失败 |
| 401 | 未登录、会话过期、id_token 校验失败、userinfo sub 不一致 |
| 403 | CSRF 校验失败 |
| 409 | 好友/申请冲突（已申请、已是好友、对方已申请） |
| 422 | 参数校验失败（搜索串、消息内容、分页参数越界） |
| 502 | IdP 响应缺令牌、userinfo 请求失败 |
| 302 | 登录/登出跳转 |

## 会话 Cookie

名称 `lichat_session`，属性 `HttpOnly + SameSite=Lax + Path=/`，生产加 `Secure`，最大存活 7 天（滑动 2 小时）。
