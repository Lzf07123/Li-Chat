# Li&Chat ↔ Li&Pass OIDC 对接文档

本文档说明 Li&Chat（依赖方 RP）与 Li&Pass（身份提供方 IdP）的对接方式，把门户《OIDC 对接指南》的接口契约与 Li&Chat 的实现一一对照，供联调、注册客户端与上线验收使用。

## 1. 角色与总体架构

- Li&Chat 是 OIDC 依赖方：浏览器只与 Li&Chat 通信，登录时短暂跳转 Li&Pass，回调后由 Li&Chat 建立本地会话。
- Li&Pass 是 IdP：仅支持 `response_type=code` + PKCE `S256`；scope 支持 `openid`、`profile`、`email`；`access_token` 15 分钟、`id_token` 5 分钟，不提供刷新令牌——因此登录完成后本地会话是唯一鉴权依据。
- 门户端点一律从发现文档读取（`GET /.well-known/openid-configuration`），其中 authorize / token / userinfo / jwks / end-session 五个端点。

> 已知门户配置（遗留风险）：发现文档声明的 `issuer` 为 `http://account.lizf.cn`，传输层实际走 `https://account.lizf.cn`。Li&Chat 把五个传输端点升级为 https 调用，`iss` 仍按发现文档原文校验；等门户把 issuer 改为 https 后即可完全收敛（见 `docs/security.md`）。

## 2. Li&Chat 实现的接口（对照指南 §2）

| 接口 | 路径/方法 | 行为 |
| --- | --- | --- |
| 授权回调 | `GET /oidc/callback` | 校验 `state` 且单次使用（取出即删、600 秒过期）；`error=access_denied`/`error_description=account_blocked` 按失败处理并提示；`code + code_verifier + client_secret` 换令牌；`id_token` 按 `kid` 选钥 RS256 验签并校验 `iss`、`aud=client_id`、`nonce`、`iat/exp`；`access_token` 只用于 userinfo 且不校验其 `aud`；userinfo `sub` 与 id_token `sub` 一致后 upsert 用户，本地会话绑定 `(sub, sid)`（`sid` 取自 id_token）；黑名单的 403 映射为友好提示 |
| 回程登出 | `POST /oidc/backchannel-logout` | form 字段 `logout_token`；`kid` 选钥验签、`iss`、`aud=client_id`、`iat` 120 秒新鲜窗口 + `exp` 有效性、`jti` 已见缓存防重放（内存/Redis）、`events` 必须含 backchannel-logout；优先清 `(sub,sid)` 会话，`sid` 缺失或未命中时回退删除该用户全部会话并断开 WS；成功返回 2xx JSON `{"status":"ok"/"ignored"}` |
| 登出回跳 | `GET/POST /oidc/post-logout` | 兼容两种门户实际行为：带 `state`（query/form/JSON/原始 body）→ HMAC 验签后 302 首页；带 `logout_token` → 走与回程登出相同的完整校验，清会话断 WS 后返回 **200 HTML 跳转页**（meta refresh + JS 回 `/`，浏览器落回登录卡片页，门户侧仍 2xx）；无有效凭据返回 400 并记录来源/字段名（不落令牌值） |
| RP 发起登出 | `POST /oidc/logout`（CSRF） | 清本地会话并断开 WS → 302 门户 `end-session`（带 `id_token_hint` + `client_id` + `post_logout_redirect_uri` + HMAC 签名 `state`）→ 门户展示「退出所有会话/仅退出当前网站」确认页 → 回跳 `/oidc/post-logout` 验签 |
| 授权单飞 | `GET /oidc/login` | 同一浏览器复用未完成的 auth state（HttpOnly Cookie `lichat_auth`）；任一授权完成后即删除 state 并清 Cookie，其余授权确认页随之作废，防止多个确认页并行放行出多个会话 |

前端行为：任何接口 401 与 WS 4401 一律回落到 `/` 登录卡片页，**不会自动发起**授权流程；用户手动点击「使用 Li&Pass 登录」才进入授权。

## 3. 门户应用注册配置（对照指南 §5）

在门户「授权网站管理」创建应用时按下表登记（地址必须与代码使用值**逐字符一致**，含协议/路径/端口）：

| 门户表单字段 | Li&Chat 对应值 | 说明 |
| --- | --- | --- |
| 回调地址 | `LICHAT_OIDC_REDIRECT_URI`（dev 默认 `http://localhost:8000/oidc/callback`；生产 `https://<域名>/oidc/callback`） | 必填，精确匹配 |
| 回程登出地址 | `https://<域名>/oidc/backchannel-logout` | 推荐；生产必须 https 且公网可达（不得回环/私网） |
| 登出回跳白名单 | `LICHAT_OIDC_POST_LOGOUT_REDIRECT_URI`（dev 默认 `http://localhost:8000/`；生产 `https://<域名>/`） | 使用 RP 登出则必填，精确匹配 |
| 客户端类型 | 机密客户端 | `LICHAT_OIDC_CLIENT_SECRET` 只存服务端，不落前端 |
| scope | `openid profile email`（`LICHAT_OIDC_SCOPE`） | 邮箱用于资料同步与按邮箱搜索；未验证邮箱不阻塞登录，仅存 `email_verified` 标记 |

> 实际联调确认：门户把回程登出令牌以 form 字段 `logout_token` POST 到「登出回跳地址」而非浏览器回传 `state`。Li&Chat 的 `/oidc/post-logout` 已按此实测行为兼容处理（见 §2），无需额外改门户配置。

## 4. 接入验收清单（指南 §2.4 逐项对照）

- [x] 回调地址已登记且与代码使用值逐字符一致（`LICHAT_OIDC_REDIRECT_URI` 单一来源）
- [x] 回调校验 `state`；`error=access_denied`（含 `account_blocked`）按失败处理
- [x] 换令牌带 PKCE `code_verifier`（机密客户端另带 `client_secret`）；授权码一次性使用
- [x] `id_token` 完整校验（验签/`kid` 选钥/`iss`/`aud=client_id`/`nonce`/`iat`/`exp`）；`access_token` 仅用于 userinfo 且不按 `client_id` 校验 `aud`
- [x] 本地会话绑定 `(sub, sid)`（`sid` 取自 `id_token`）
- [x] 登出通道二选一：已实现回程登出
- [x] 回程登出：验签、`iss`/`aud`、120 秒新鲜窗口、`jti` 防重放、`events` 检查、按 `(sub,sid)` 下线、成功返回 2xx
- [x] 使用 RP 发起登出时已登记登出回跳白名单（精确匹配）
- [x] 网站黑名单：授权跳回 `access_denied`、换令牌与 userinfo 返回 403，均按失败处理

## 5. 上线注意事项

- `LICHAT_ENV=prod` 时强制 `LICHAT_SESSION_SECRET` ≥ 32 字符，并启用 Secure Cookie；生产必须 https。
- 回程登出地址需公网 https 可达（门户强制校验，不指向回环/私网）。
- 多副本需共享数据库（当前 SQLite 为本地卷只能单副本，切 PostgreSQL + Alembic 后可行）与 `LICHAT_REDIS_URL`（jti 防重放 + 跨副本登出广播）。
- 登录接口限流仍是待办（见 `docs/security.md` 遗留风险）。
- 代码更新后容器部署需 `docker compose up -d --build` 重建镜像（静态前端与后端均打包在镜像内）。
- 完整环境变量清单与部署步骤见 [部署指南](deployment.md)，安全设计见 [安全设计清单](security.md)。

## 6. 联调步骤

1. 门户注册客户端并登记 §3 的三个地址，拿到 `client_id`/`client_secret`。
2. `cp .env.example .env`，填入 `LICHAT_OIDC_*`；`LICHAT_ENV=dev` 时本地 http 可跑通登录（prod 需 https）。
3. `uv run uvicorn app.main:app --reload`，浏览器打开首页走「登录 → 授权 → 回调 → 会话」闭环。
4. 验证登出三条路径：RP 登出（回跳验签）、回程登出（门户登出即被踢下线）、登出回跳（落回登录卡片页）。
