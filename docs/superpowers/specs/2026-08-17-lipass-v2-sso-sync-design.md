# Li&Pass V2 SSO 契约同步设计规格

> 日期：2026-08-17 ｜ 状态：设计中 ｜ 分支：`codex/lipass-v2-sync`

## 1. 目标

Li&Pass 门户发布重大更新（见附件「OIDC 对接指南」），Li&Chat 作为依赖方（RP）需同步
对齐新契约，补齐验收清单中当前缺失的项，并跟随新的双语义登出模型。

## 2. 现状与事实

### 2.1 已实现且已合规的部分（不动）

- 发现文档缓存读取全部端点，issuer/端点不自行拼接；`issuer` 原文严格校验。
- 授权码 + PKCE S256：`secrets.token_urlsafe(48)`、单次使用 state（取出即删）、nonce 校验。
- id_token：按 `kid` 从 JWKS 选钥 RS256 验签、`iss`/`aud=client_id`/`nonce`/`iat`/`exp`
  校验、密钥轮换自动刷新；access_token 只用于 userinfo、不按 client_id 校验 aud。
- 本地会话绑定 `(sub, sid)` 与 `acr`；回程登出验 iss/aud/120 秒新鲜窗口/jti 防重放/
  `events`，按 `(sub, sid)` 下线（sid 缺失/未命中回退删全部），断 WS 并跨副本广播。
- RP 发起登出：`id_token_hint` + `client_id` + `post_logout_redirect_uri` + 签名 state，
  回跳验签；`error=access_denied`（含 `account_blocked`）回调失败处理。
- 机密客户端 `client_secret` 走 form 字段（`client_secret_post`）。

### 2.2 真实 IdP 现状（2026-08-17 实测）

`https://account.lizf.cn/.well-known/openid-configuration` 返回：

- `issuer` 与五个端点已收敛为 **https 字面值**（此前声明 http、80 端口 301）；
- 新增 `token_endpoint_auth_methods_supported: ["none","client_secret_post"]`、
  `claims_supported: ["sub","email","email_verified","nickname","name","picture","acr","sid"]`；
- `backchannel_logout_supported: true`、`frontchannel_logout_supported: false`。

### 2.3 当前缺口（本次补齐）

| # | 缺口 | 影响 |
| --- | --- | --- |
| 1 | id_token 未校验 `at_hash`（指南 §2.2/§2.4/§3.3 必选：`base64url(SHA256(access_token) 左 16 字节)`） | 验收清单「id_token 校验完整」不通过 |
| 2 | token 端点 403 黑名单现返回 `{"error":"access_denied","error_description":"该账号已被此网站限制访问"}`（RFC 6749 格式），现代码把 `access_denied` 映射为「登录凭证已失效」 | 封禁用户看到错误提示 |
| 3 | 未提供「仅登出本网站」通道（指南 §8.1 要求两种语义分开，参考实现提供两个按钮） | 只想退出本站时仍被带去门户确认页 |
| 4 | `tests/fixtures/real_discovery.json` 还是旧的 http 文档 | 测试夹具与生产事实漂移 |

## 3. 方案

### 3.1 at_hash 校验（`app/oidc/tokens.py`）

- `validate_id_token(token, nonce)` → `validate_id_token(token, nonce, access_token)`。
- 解码后校验 `claims["at_hash"]` 存在且等于
  `base64.urlsafe_b64encode(sha256(access_token.encode()).digest()[:16]).rstrip(b"=").decode()`；
  不匹配或缺失抛 `TokenValidationError("at_hash mismatch")`（指南明确 IdP 恒携带，
  缺失按失败关闭处理）。
- 回调处把 `access_token` 一并传入。

### 3.2 token 端点封禁映射（`app/sso/routes.py`）

- 回调 `TokenExchangeError` 分支：`error_code in ("account_blocked", "access_denied")`
  均映射「该账号已被此网站限制访问」；其余保持「登录凭证已失效，请重新登录」。
- `provider._safe_json` 保留 403 无 `error` 字段时的 `account_blocked` 兜底。

### 3.3 双语义登出（`app/sso/routes.py` + `static/app.js`）

- 提取 `_clear_local_session(request, db)`：删除当前会话、断该用户 WS、Redis 广播登出，
  供两个登出端点复用。
- 新增 `POST /oidc/logout-local`（CSRF）：仅清本地会话，302 回 `/`，**不**调
  `end-session`；`POST /oidc/logout` 保持「登出 SSO」语义不变。
- 前端「退出登录」确认弹窗提供两个动作：`仅退出本网站`（`logout-local`）与
  `退出 SSO`（原 logout）；共用 `submitLogoutForm(action)`。

### 3.4 发现文档与文档同步

- `tests/fixtures/real_discovery.json` 更新为实测 https 文档（含两个新字段）。
- `app/oidc/discovery.py` 的 http→https 升级逻辑**保留**为防御性兜底，注释改为
  「Issuer 已收敛 https，此逻辑当前不生效，防 IdP 回退」。
- 同步 docs/api.md（新端点与双语义）、docs/security.md（at_hash、access_denied 映射、
  遗留风险中 issuer https 已收敛）、docs/deployment.md（发现文档现状）。

## 4. 接口与数据模型

- 新增端点：`POST /oidc/logout-local`（CSRF）→ 302 `/`；无新表、无模型字段变更。
- 不新增环境变量。

## 5. 安全影响

- at_hash 校验把 access_token 与 id_token 绑定，防止令牌替换类攻击——安全增强。
- `access_denied` 映射只影响提示文案，不改变失败关闭行为。
- `logout-local` 与 `logout` 同等要求 CSRF、同样断 WS/广播，不降低登出强度；仅
  减少 SSO 联邦范围，安全边界不变。

## 6. UI 变更

- 退出登录弹窗两动作（参考 portal 端「登出 SSO / 仅登出本网站」二分语义）。

## 7. 验收标准

- [ ] mock IdP 的 id_token 携带正确 `at_hash`，登录闭环通过；篡改/缺失 `at_hash` 返回 401
- [ ] token 端点 403 `access_denied` 映射封禁提示（有测试）
- [ ] `logout-local` 清会话、断 WS、不调 `end-session`；无 CSRF 返回 403（有测试）
- [ ] `logout`（SSO）行为不变，现有测试全绿
- [ ] `pytest -q` / `ruff check .` / `mypy app` 全绿
- [ ] real_discovery 夹具与实测文档一致，解析与 https 升级测试通过
