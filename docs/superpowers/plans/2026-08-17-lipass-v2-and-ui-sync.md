# 实施计划：Li&Pass V2 契约同步 + 模板 V1.2 UI 同步

> 日期：2026-08-17 ｜ 分支：`codex/lipass-v2-sync` ｜ 依赖规格：
> [SSO 同步](./2026-08-17-lipass-v2-sso-sync-design.md)、
> [UI 同步](./2026-08-17-design-template-v12-ui-sync-design.md)

全部 Task 遵循 TDD：先写失败测试 → 验证红 → 最小实现 → 验证绿 → 独立提交。
并行约束：无并行 Task，全部串行（共享 sso/routes.py、static/app.js）。

## T1 SSO 令牌校验加固（at_hash + token 403 封禁映射）

- Consumes：`app/oidc/tokens.py`、`app/sso/routes.py`、`tests/fixtures/mock_idp.py`
- Produces：上述三文件；新增 `tests/test_provider.py` / `tests/test_login.py` 用例
- 步骤：
  - [x] 测试红：mock_idp 补 at_hash 后，新增「篡改/缺失 at_hash 拒绝」用例
  - [x] 实现：`validate_id_token` 增加 access_token 参数并校验 at_hash
  - [x] 测试红：token 端点 403 `access_denied` 映射封禁提示用例
  - [x] 实现：回调映射 `access_denied`/`account_blocked` → 封禁提示
  - [x] 全量绿：`uv run pytest -q tests/test_provider.py tests/test_login.py`

## T2 双语义登出（后端 logout-local + 前端弹窗）

- Consumes：`app/sso/routes.py`、`static/app.js`
- Produces：上述两文件；新增 `tests/test_logout.py` 用例
- 步骤：
  - [x] 测试红：`logout-local` 清会话、不调 end-session、无 CSRF 403
  - [x] 实现：`_clear_local_session` 抽取 + `POST /oidc/logout-local`
  - [x] 前端：登出确认弹窗两动作（仅退出本网站 / 退出 SSO）
  - [x] 全量绿：`uv run pytest -q tests/test_logout.py tests/test_backchannel.py`

## T3 发现文档夹具与 docs 同步

- Consumes：`tests/fixtures/real_discovery.json`、`tests/test_real_discovery.py`、
  `app/oidc/discovery.py`（仅注释）、docs/api.md、docs/security.md、docs/deployment.md
- Produces：上述文件
- 步骤：
  - [x] 夹具更新为实测 https 文档（含新字段）
  - [x] `test_real_discovery.py` 更新断言；保留 http 文档的升级兜底用例
  - [x] discovery.py 注释更新（issuer 已 https，升级逻辑为兜底）
  - [x] 同步 docs/api.md、docs/security.md、docs/deployment.md
  - [x] 全量绿：`uv run pytest -q tests/test_real_discovery.py tests/test_discovery.py`

## T4 UI 令牌与组件（style.css）

- Consumes：`static/style.css`
- Produces：`static/style.css`
- 步骤：
  - [x] 按钮着色令牌 + `.btn-primary` 半透明/描边/`::after` 扫光 + `@keyframes`
  - [x] `.auth-halo` / `.brand-glow` 与对应 keyframes（reduced-motion 静止）
  - [x] 对比度核算脚本复跑，按钮文字对底色 ≥4.5
  - [x] `test_frontend.py` 既有断言不回归（令牌文本变化同步检查）

## T5 前端结构（app.js）与设计系统文档

- Consumes：`static/app.js`、`design-system/chat/BRAND.md`、`design-system/chat/MASTER.md`
- Produces：上述三文件
- 步骤：
  - [x] renderLoggedOut halo/glow 结构
  - [x] BRAND.md 槽位 20→22 + V1.2 注记 + 不采用项理由
  - [x] MASTER.md 令牌/组件/验收状态回写

## T6 收尾（CHANGELOG + 全量验证 + 预览 + 合并）

- Consumes：CHANGELOG.md、全仓库
- Produces：CHANGELOG.md、`design-system/chat/preview/` 截图、合并提交
- 步骤：
  - [x] CHANGELOG「未发布」分区更新
  - [x] `uv run pytest -q`、`uv run ruff check .`、`uv run mypy app` 全绿（保留输出）
  - [x] 浏览器视觉冒烟：认证页明暗两套截图存 preview/
  - [x] 分任务提交后合并 main（保留 merge 记录）
