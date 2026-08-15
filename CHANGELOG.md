# Changelog

## v0.1.0 — 2026-08-15

首个里程碑：Li&Pass OIDC 单点登录，按五个版本本地迭代交付，55 个测试、ruff、mypy 全绿。

- v1：项目骨架、配置、日志、数据库、发现文档客户端（含本地模拟 IdP）
- v2：授权码 + PKCE 登录闭环、id_token 校验、用户落库
- v3：本地会话（HttpOnly Cookie、滑动/绝对过期）、受保护路由、CSRF
- v4：RP 登出、回程登出（jti 防重放）、WebSocket 认证桥接
- v5：同源前端、真实发现文档校验、SQLite 目录自动创建、文档补全

已知事项：真实登录待 Li&Pass 门户注册 client_id/client_secret 后联调；上线前清单见 `docs/deployment.md`。
