# 接口文档

## REST

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/healthz` | 无 | 健康检查，返回 `{"status":"ok"}` |
| GET | `/oidc/login?redirect_after=/` | 无 | 生成 PKCE 并 302 到授权页；`redirect_after` 仅接受站内相对路径 |
| GET | `/oidc/callback` | 无 | 授权回调（code/state/error/error_description），成功 302 回 `redirect_after` 并种会话 Cookie |
| GET | `/oidc/error?message=` | 无 | 登录错误页，返回 `{"message": ...}` |
| POST | `/oidc/logout` | CSRF | 清本地会话，302 到 IdP `end-session` |
| GET | `/oidc/post-logout?state=` | 无 | 门户登出回跳，验签后 302 首页 |
| POST | `/oidc/backchannel-logout` | 无 | 门户服务器间调用，form 字段 `logout_token`，返回 `{"status":"ok"}` 或 `{"status":"ignored"}` |
| GET | `/api/me` | 会话 | 当前用户 `{sub, nickname, name, picture, email, csrf_token}` |
| GET | `/` | 无 | 同源前端页面 |

## WebSocket `/ws`

- 握手携带同源 Cookie，会话无效在 accept 后以 **4401** 关闭。
- 连接成功后服务端推送 `{"type":"hello","sub":"..."}`。
- 客户端发 `{"type":"ping"}` 收到 `{"type":"pong"}`，前端每 25 秒心跳一次。
- 回程登出会主动以 4401 断开该用户连接，前端据此跳转登录。

## CSRF 约定

对非安全方法（如 `POST /oidc/logout`）二选一携带：请求头 `X-CSRF-Token: <csrf_token>`，或表单字段 `csrf_token`。令牌从 `/api/me` 获取。

## 状态码约定

| 状态码 | 含义 |
| --- | --- |
| 400 | 回调 state 无效/重放、logout state 或 logout_token 校验失败 |
| 401 | 未登录、会话过期、id_token 校验失败、userinfo sub 不一致 |
| 403 | CSRF 校验失败 |
| 502 | IdP 响应缺令牌、userinfo 请求失败 |
| 302 | 登录/登出跳转 |

## 会话 Cookie

名称 `lichat_session`，属性 `HttpOnly + SameSite=Lax + Path=/`，生产加 `Secure`，最大存活 7 天（滑动 2 小时）。
