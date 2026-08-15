# 安全设计清单

| 要求 | 实现 | 位置 |
| --- | --- | --- |
| 授权码 + PKCE S256 | verifier 用 `secrets.token_urlsafe(48)`，challenge 为 SHA256 的 base64url | `app/oidc/pkce.py` |
| state/nonce 校验且单次使用 | 服务端存储，取出即删除，10 分钟过期 | `app/oidc/state.py` |
| redirect_uri 精确匹配 | 只从配置读取，不拼接、不做前缀匹配 | `app/config.py` |
| 开放重定向防护 | `redirect_after` 仅允许站内相对路径 | `app/sso/routes.py:_safe_redirect_after` |
| id_token 校验 | iss、aud=client_id、nonce、RS256、iat/exp、按 kid 从 JWKS 选钥，密钥轮换时自动刷新 | `app/oidc/tokens.py` |
| access_token 用途限定 | 只用于调用 userinfo，不在本地校验 aud | `app/oidc/provider.py` |
| 本地会话 | HttpOnly + SameSite=Lax（生产 Secure）、滑动 2h/绝对 7d、绑定门户 sid | `app/auth/session.py` |
| CSRF | 双提交令牌，支持请求头与表单字段，`secrets.compare_digest` 比对 | `app/auth/deps.py` |
| RP 登出 state | HMAC-SHA256 签名，回跳验签 | `app/sso/signing.py` |
| 回程登出 | 验 iss/aud/120 秒新鲜窗口/jti 防重放/events，命中清会话并断 WS | `app/sso/routes.py`、`app/sso/replay.py` |
| 账号封禁 | `account_blocked` 与 403 映射为友好提示，不泄露细节 | `app/sso/routes.py` |
| 生产密钥强度 | prod 环境会话密钥不足 32 字符直接拒绝启动 | `app/config.py` |
| 日志 | 结构化日志，仅记录错误码与 id，不落令牌 | `app/logging.py` |

## 遗留风险（上线前处理）

- jti 防重放与会话状态为进程内实现，多副本需 Redis（见部署指南）。
- 登录接口暂无频率限制，需在网关或应用层加限流。
- 数据库迁移尚未引入 Alembic。
- 发现文档 issuer 的 http/https 不一致问题待 IdP 侧修正。
