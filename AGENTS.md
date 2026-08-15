# Li&Chat 项目协作手册（多 Agents）

> 本文件是给后续 AI Agent（Codex 等）的「项目宪法」。**新会话必须先完整读完本文件再动手；子 agent 接单后同样先读本文件与第二节事实来源。** 人类开发者同样适用。

## 一、项目是什么

Li&Chat 是基于 OIDC SSO（Li&Pass）的小圈子即时通讯。后端 FastAPI + SQLAlchemy 2.0（异步；SQLite 开发、PostgreSQL 生产），前端为同源托管的原生静态页（`static/`）。当前里程碑：统一单点登录（授权码 + PKCE、本地会话、三路径登出、WebSocket 认证桥接）已交付；后续里程碑见 [README.md](./README.md) 路线图。

**这是身份接入型产品**：任何改动都不得降低认证强度、破坏 OIDC 契约、绕过 CSRF/回程登出校验或泄露用户数据。安全回归的代价高于功能进度。

## 二、事实来源（动手前按顺序读）

| 内容 | 位置 |
| --- | --- |
| 产品全貌、快速开始、路线图 | [README.md](./README.md) |
| 最近改动与历史决策 | [CHANGELOG.md](./CHANGELOG.md)（先看顶部）、`git log --oneline -20` |
| 架构与模块职责 | [docs/architecture.md](./docs/architecture.md) |
| REST/WS/CSRF/状态码契约 | [docs/api.md](./docs/api.md) |
| 环境变量、部署与上线清单 | [docs/deployment.md](./docs/deployment.md) |
| 安全设计清单与遗留风险 | [docs/security.md](./docs/security.md) |
| 历史设计规格与实施计划 | [docs/superpowers/specs/](./docs/superpowers/specs/)、[docs/superpowers/plans/](./docs/superpowers/plans/) |
| 品牌与视觉规范 | [design-system/](./design-system/)（详见第九节） |

**文档与代码冲突时：代码是运行事实，文档是意图。** 先核对差异，再决定改哪边；改代码必须同步文档（见「收尾」）。

## 三、架构地图

```text
app/
├── main.py        # 应用装配、生命周期（建表/建目录）、/ws、/healthz、静态挂载
├── config.py      # LICHAT_* 环境变量；prod 校验会话密钥强度
├── db.py          # 异步引擎与会话工厂
├── models.py      # users / auth_states / sessions 三张表
├── logging.py     # 结构化日志（不落令牌）
├── timeutil.py    # 时间工具
├── auth/          # 本地会话生命周期、Cookie、get_current_user / require_csrf
├── oidc/          # 依赖方实现：发现文档、PKCE、状态、令牌校验、用户同步
├── sso/           # /oidc/* 路由、登出签名、jti 防重放
├── ws/            # 进程内 WebSocket 连接管理
└── api/           # /api/me
static/            # 同源前端：index.html / app.js / brand.js / theme.js / ambient.js / style.css
tests/             # 62 个测试 + 本地模拟 IdP（零外网依赖）
docs/              # 架构、接口、部署、安全、设计规格与实施计划
design-system/     # 品牌设计（chat/ 项目方案 + template/ Li-Design 子模块）
Dockerfile         # 容器镜像（python:3.12-slim + uv，非 root）
docker-compose.yaml # 容器编排（单服务 + SQLite 命名卷 + healthcheck）
```

关键事实：单进程 FastAPI 同源托管前端；浏览器只与 Li&Chat 通信，登录时短暂跳转 Li&Pass。OIDC 路由在 `/oidc/*`，会话接口 `/api/me`，实时通道 `/ws`（握手携带同源 Cookie）。环境变量前缀 `LICHAT_`。

## 四、硬性规则

1. **秘密不入库**：`.env`、`data/` 已被 gitignore；配置变更只改 `.env.example`，并同步 [docs/deployment.md](./docs/deployment.md) 的环境变量表。
2. **安全不降级**：涉及登录、会话、OIDC、令牌、CSRF、登出签名、jti 防重放的改动必须保持 [docs/security.md](./docs/security.md) 的防护与测试覆盖。
3. **测试零外网**：所有测试走 `httpx.ASGITransport` 与本地模拟 IdP（`tests/fixtures/mock_idp.py`），不监听端口、不访问外网；新功能沿用此模式。
4. **数据库变更**：当前由 lifespan 自动建表、尚无 Alembic；改模型必须保证建表逻辑与三表结构同步。引入 Alembic 后，一切 schema 变更必须写迁移并验证升降级往返。
5. **UI 改动先读设计规范**：见第九节；令牌以实际落地文件为准（当前 `static/style.css`）；动效尊重 `prefers-reduced-motion`。
6. **命名**：品牌显示名 `Li&Chat`；技术标识统一 `lichat`（环境变量前缀、Cookie 名、数据库文件、目录、卷名）。不新增其他标识。
7. **完成 = 验证 + 文档**：声称完成前必须给出验证输出（见第七节）；功能合并前更新 CHANGELOG 与相关文档。
8. **遵循既有分层**：路由保持薄，业务逻辑放对应模块；不在路由里堆业务。

## 五、多 Agents 协作规范

**总原则：单一事实来源、一个任务一个 owner、并行任务零文件重叠。**

角色划分：

- **root agent**：拆解任务、指派、收集证据、验收，并对用户交付最终结果。
- **sub-agent**：执行一个明确的 Task，交付验证证据，不越权扩张。

派活规则：

1. 只派**具体、有边界**的 Task；附完整上下文，确保子 agent 无需猜测项目事实。
2. Task 必须写清接口：Consumes（依赖/输入文件）与 Produces（产出文件/契约），**精确到文件**，验收标准可独立验证。
3. 并行派发的 Task 之间**不得重叠同一文件或同一契约**；有依赖关系一律串行。
4. 并行数量不超过可用并发槽位；共享工作区意味着改动即时可见，先认领再动手。

执行纪律（每个 agent 都适用）：

- 动手前先读本文件与第二节事实来源；不清楚就问 root，**不许用猜测代替调查**。
- 不擅自扩大任务范围；需要新决策时回报 root 或停下询问用户。
- 验证才算完成：跑第七节命令并保留输出；失败必须说明原因与证据。
- 遇阻先探原因（读代码、跑最小复现、查日志），带着证据汇报，不静默停摆。
- 不做破坏性操作（`rm -rf`、force push、动他人提交）；不动他人未提交的改动；子 agent 不自行切换分支或合并 main。

评审与验收：

- 每个 Task 完成后做**两段评审**：① 是否符合接口/安全/设计规范；② 质量门禁（pytest/ruff/mypy）是否全绿。
- root 只依据**验证输出**验收，不接受无证据的「完成」声称。

冲突处理：

- 文档与代码冲突 → 以代码为事实，回写文档。
- agent 之间意见冲突 → 提交 root，用可复现的事实裁决。
- 与用户意图冲突或需要新权限/外部协调 → 停下当前动作，向用户说明并请求指示。

## 六、标准工作流（每个功能走一遍）

1. **调查**：按第二节读事实来源；搜 `docs/superpowers/specs/` 有无历史设计；`git branch -a` 与 CHANGELOG 顶部确认无人正在做同一件事。
2. **设计（非平凡改动必做）**：写 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`——目标、现状、方案取舍、接口/数据模型、安全影响、UI（引用设计系统）、验收标准。
3. **计划（多步任务必做）**：写 `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`，按 Task 拆分；每个 Task 有精确文件、接口（Consumes/Produces）、可独立验证的交付物与 checkbox 步骤；TDD。
4. **隔离实现**：`git worktree add .worktrees/<topic> -b codex/<topic>`（或直接开分支）；每个 Task：写失败测试 → 验证红 → 最小实现 → 验证绿 → 独立提交。多任务按第五节派子 agent 逐 Task 实现。
5. **全量验证**：跑第七节命令；涉及真实登录/部署的在真机冒烟。
6. **收尾**：更新 [CHANGELOG.md](./CHANGELOG.md) 对应分区；同步 README/architecture/api/deployment/security 中受影响的部分；`docs:` 提交；合并 main。

## 七、验证命令

```bash
uv sync --dev
uv run pytest -q      # 62 个测试（当前数量），必须全绿
uv run ruff check .
uv run mypy app
```

本地冒烟：

```bash
uv run uvicorn app.main:app --reload
curl -fsS http://localhost:8000/healthz   # {"status":"ok"}
```

> 测试不依赖外网；真实登录联调需先在 Li&Pass「授权网站管理」注册 client_id/client_secret（见 [docs/deployment.md](./docs/deployment.md)）。

容器冒烟：

```bash
docker compose up -d --build
docker compose ps      # 等待 healthy
curl -fsS http://127.0.0.1:8000/healthz
docker compose down
```

## 八、提交与分支

- 分支：`codex/<topic>`（kebab-case），完成后合并回 `main`（保留 merge 记录）。
- 提交消息：`<type>: <中文简述>`；type 用 `feat`/`fix`/`perf`/`docs`/`test`/`refactor`/`chore`。每个 Task 独立提交。
- CHANGELOG 分区：破坏性变更 / 功能 / 安全加固 / 行为变更 / 缺陷修复。

## 九、品牌与设计规范（首次设计专属流程）

**当前状态：首次设计已完成（2026-08-16）。** 视觉决策以 [design-system/chat/BRAND.md](./design-system/chat/BRAND.md) 与 [MASTER.md](./design-system/chat/MASTER.md) 为唯一事实来源，令牌在 `static/style.css`、品牌单点在 `static/brand.js`；UI 改动先读这两份文档，不再依赖 `template` 子模块（可经评审后移除）。

`design-system/template/` 是 [Li-Design](https://github.com/Lzf07123/Li-Design) 的子模块，**只在 Li&Chat 第一次做视觉设计时参考**，不参与日常开发。

首次设计流程：

1. 读 [REUSABLE-BRAND-SCHEME.md](./design-system/template/REUSABLE-BRAND-SCHEME.md) 与 [reusable-tokens.template.css](./design-system/template/reusable-tokens.template.css)，按槽位表填 20 项（名称、定位、主色、语义色、字体、Logo、氛围浓度等）。
2. 在项目内产出 `design-system/chat/BRAND.md`（品牌内核 + 已填槽位）与 `design-system/chat/MASTER.md`（令牌、组件、页面模式快照）。
3. 令牌落地：当前前端是 `static/` 原生静态页，模板假定 React/Vite 结构，落地时把 Tailwind 令牌映射为 `static/style.css` 的 CSS 变量/类；若引入正式前端框架，先在设计规格中确定目录结构再落地。
4. 过 [REUSABLE-BRAND-SCHEME.md](./design-system/template/REUSABLE-BRAND-SCHEME.md) 的 Pre-Delivery Checklist 后收尾。

**首次设计完成后：一切以 `design-system/chat/` 为唯一事实来源**，不再依赖 `template`；可经评审后 `git rm design-system/template` 移除子模块。子模块日常同步用 `git submodule update --init`（对齐锁定提交），`--remote` 需评审后谨慎使用。

## 十、常见坑（来自交付历史与遗留风险）

- **issuer 字面量**：发现文档声明 `http://account.lizf.cn`，传输层走 `https://account.lizf.cn`；校验按发现文档原文，不自行改写（待 IdP 修正，见 [docs/security.md](./docs/security.md) 遗留风险）。
- **prod 会话密钥**：`LICHAT_SESSION_SECRET` 不足 32 字符直接拒绝启动；Secure Cookie 只在 prod 启用。
- **WS 认证桥接**：会话无效在 accept 后以 4401 关闭；前端把 4401 视为被登出。改握手逻辑别破坏这条约定。
- **开放重定向**：`redirect_after` 仅允许站内相对路径（`_safe_redirect_after`）；新回跳参数沿用同一思路。
- **进程内状态**：jti 防重放与会话状态是进程内实现，多副本部署需 Redis（上线前事项）。
- **登录限流**：登录接口目前无限流，需在网关或应用层补（上线前事项）。
- **`.env` 按工作目录解析**：别在仓库根放会干扰测试的 `.env`。
- **静态目录按包路径解析**：`static/` 相对 `app/main.py` 定位，与运行目录无关。
- **SQLite 测试夹具 ≠ PostgreSQL**：生产切 PostgreSQL 后，JSON/时间/外键语义需真库验证。
- **容器必须单 worker**：镜像 CMD 固定 `--workers 1`，多 worker 会破坏回程登出/WS 推送（进程内状态）；Redis 外置前不可扩副本。
- **容器内勿用 `uv run` 启动服务**：`uv run` 会按默认组重新同步、把 dev 依赖拉进运行时；直接 `uv sync --frozen --no-dev` 后用 `.venv/bin/uvicorn`。
- **容器本地冒烟用 `LICHAT_ENV=dev`**：`prod` 校验 ≥32 字符密钥并启用 Secure Cookie，http 下登录会失败；生产必须 https + `LICHAT_ENV=prod`。
