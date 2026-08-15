# Li&Chat UI 重构设计规格（首次设计实例化）

- 状态：已批准（方向确认 2026-08-16）
- 日期：2026-08-16
- 品牌：Li&Chat
- 依据：[Li-Design V1.0](../../../design-system/template/REUSABLE-BRAND-SCHEME.md) + [AGENTS.md](../../../AGENTS.md) 第九节

## 1. 目标与范围

按 Li&Design 模板完成 Li&Chat 的**首次设计实例化**，把当前临时视觉重构为有令牌、有品牌氛围、明暗双主题的成品 UI。本次只改 `static/` 前端与配套文档/测试，不动后端契约。

**范围内：**

- `static/index.html`、`static/style.css`、`static/app.js` 重构
- 新增 `static/brand.js`（品牌单点）、`static/theme.js`（主题）、`static/ambient.js`（氛围层）、`static/favicon.svg`
- 新增 `design-system/chat/BRAND.md`、`design-system/chat/MASTER.md`
- 扩展 `tests/test_frontend.py` 静态断言

**不在范围：**

- React/Vite 迁移（若引入，另立规格评审）
- `/oidc/error` 等 JSON 响应页面的视觉化
- 里程碑二的好友与聊天界面（组件基座为它预留，但不实现）

## 2. 现状与问题

当前前端是单卡片三态页（未登录/已登录/连接状态），约 70 行 CSS、100 行 JS。问题：无令牌体系（散落 hex 值）、无暗色模式、临时蓝 `#2f6fed` 未经校验、无品牌氛围层、无 favicon 与 `theme-color`、文案硬编码在 JS 中、连接状态无无障碍标注。

## 3. 方案取舍（已确认）

| 决策点 | 结论 | 理由 |
| --- | --- | --- |
| 主色 | `#2563EB` 信使蓝 | ui-ux-pro-max 规则库「Chat & Messaging App」首选（Messenger blue），白底对比度 5.1:1；与 Li&Pass `#0369A1` 同族而异、按产品域落位 |
| 技术栈 | 保持原生静态页 | 零构建、低风险；AGENTS.md 已约定把 Tailwind 令牌映射为 CSS 变量 |
| 深色模式 | 本次做全 | 模板核心验收项；聊天产品强需求 |
| Logo | 家族几何语法 SVG 标识 | 无现成资产；符号语法即品牌语言，兼作 favicon，不引入位图 |
| 在线状态 | 复用语义色 | 已连接=success、连接中=warning、断开=muted、失效=destructive，不新增令牌 |

## 4. 槽位表（Li&Chat 实例化）

| # | 槽位 | 取值 |
| --- | --- | --- |
| 1 | 项目显示名 | `Li&Chat` |
| 2 | 技术标识 | 基础设施 `lichat`；项目 slug 与 CSS 前缀 `chat` |
| 3 | 一句话定位 | 一次登录，直连你的小圈子 |
| 4 | 品牌承诺 | 对话只在你们之间流动；每一次登录都经 Li&Pass 验证 |
| 5 | 人格比喻 | 可靠的信使：准确送达、不多嘴、不打扰 |
| 6 | 符号隐喻 | 直线=消息通路、Z 形=对话往返、方块=消息、锁钥=私密、光斑=在线状态 |
| 7 | 主色（浅） | `#2563EB` / hover `#1D4ED8` / soft `#DBEAFE` / fg `#FFFFFF` |
| 8 | 主色（深） | `#60A5FA` / hover `#93C5FD` / soft `rgba(96,165,250,0.14)` / fg `#172554` |
| 9 | 中性色（浅） | `#F8FAFC` / `#FFFFFF` / `#F1F5F9` / `#0F172A` / `#64748B` / `#E2E8F0` |
| 10 | 中性色（深） | `#0B1220` / `#111A2C` / `#1B2740` / `#E2E8F0` / `#94A3B8` / `#263449` |
| 11 | 语义色 | 浅：success `#15803D`、warning `#B45309`、destructive `#DC2626` 及 soft；深：`#4ADE80` / `#FBBF24` / `#F87171` 及 rgba soft |
| 12 | 焦点环 | 浅 `#2563EB`、深 `#60A5FA`，2px 描边 + 2px offset，`focus-visible` 全局 |
| 13 | 字体栈 | Inter → 系统栈 → PingFang SC / 微软雅黑；不加载远程字体 |
| 14 | 标题字体 | 暂不引入 Lexend（零外部依赖）；后续如需自托管 subset 再议 |
| 15 | Logo / favicon | 几何标识「两个方块细线相连 + 右侧光斑」，内联 SVG + `favicon.svg`，透明底、无位图 |
| 16 | 令牌前缀 | `chat`（`--chat-bg` 等） |
| 17 | 主题存储键 | `chat-theme` |
| 18 | slogan / 备案 | slogan「一次登录，直连你的小圈子」；备案上线前留空，禁止假占位号 |
| 19 | 氛围浓度 | 认证页 10、登录后 8（滚动联动钩子预留）；移动端（<768px）≤6 |
| 20 | 浏览器品牌位 | `favicon.svg`、`theme-color`（浅 `#F8FAFC` / 深 `#0B1220`）、description、首帧主题脚本 |

## 5. 视觉语法与动效（继承内核）

品牌内核五原则（TRUST）、几何符号铁律、动效四模式（水平穿行/往复钟摆/正弦波形/盘旋公转）全部继承，Li&Chat 只重映射符号语义（见槽位 6）。氛围元素仅动 `transform/opacity`、`pointer-events: none`、错峰 `animation-delay`、`prefers-reduced-motion` 下单帧静止。

## 6. 架构与文件映射

| 目标文件 | 来源 / 职责 |
| --- | --- |
| `static/style.css` | 由 `reusable-tokens.template.css` 映射为原生 CSS：`--chat-*` 明暗令牌 + 组件类（无 Tailwind，`@apply` 展开为普通声明） |
| `static/brand.js` | `brand.ts` 等价物：名称 / slogan / Logo SVG / 备案占位的唯一出处 |
| `static/theme.js` | `useTheme` 等价物：读写 `chat-theme`、切换 `html.dark`；首帧脚本内联在 `index.html` |
| `static/ambient.js` | `FloatingBackground` 的 Canvas 等价物：无第三方依赖，`z-0` 垫底 |
| `static/favicon.svg` | 槽位 15 的几何标识 |
| `static/index.html` | 槽位 20 浏览器品牌位 + 首帧主题脚本 + 无障碍属性 |
| `static/app.js` | 渲染 AuthShell / AppShell，保持既有后端契约 |

## 7. 组件与页面外壳

组件类：`.btn`（primary/secondary/ghost/danger/link）、`.card`、`.badge-*`、`.notice-*`、`.label`/`.input`（预留）、`.spinner`、`.page-enter`、`.app-header`、`.site-footer`、`.avatar`、`.status-dot`、`.theme-toggle`、`.ambient-layer`。

```text
AuthShell（未登录，居中 max-w-md）
├── 品牌标识 + Li&Chat + slogan
├── 卡片：说明 + 「使用 Li&Pass 登录」主按钮
└── 底部备案位（slogan / 备案留空）

AppShell（已登录，max-w-5xl）
├── AppHeader：品牌标识 + 主题切换 + 退出
├── 内容卡：头像 + 昵称 + 连接状态（status-dot + aria-live 文本）
└── SiteFooter
```

## 8. 数据流与交互（保持既有契约）

- `/api/me`（会话）、`GET /oidc/login`、`POST /oidc/logout`（`csrf_token`）、`/ws`（无效 4401 关闭并跳登录、25 秒心跳）全部不变。
- 主题：`theme.js` 读写 `localStorage["chat-theme"]`；首帧内联脚本在 paint 前应用 `html.dark`，防止闪烁；无存储时跟随系统偏好。
- 氛围层：当前登录页无输入框，`calm`（聚焦减速）钩子预留不启用；滚动联动钩子留给里程碑二。

## 9. 无障碍与性能

- 正文对比度 ≥ 4.5:1（主色 5.1:1、muted 4.6:1 均已验算）；破坏色在 soft 底上为 4.4:1，仅限徽章等 UI 组件使用（≥3:1 达标），正文级错误提示用 surface 底（4.8:1）。
- `focus-visible` 全局 2px 主色描边；可点击目标 ≥ 44×44px；`aria-live="polite"` 标注连接状态；图标内联 SVG，无 emoji。
- 只动 `transform/opacity`；`prefers-reduced-motion` 全部单帧；移动端氛围元素 ≤6 且更淡更慢。

## 10. 测试策略

先扩展 `tests/test_frontend.py` 写失败测试再实现：

- `/` 200、text/html、含 `Li&Chat`（既有）
- `/app.js` 200、javascript（既有）
- `/style.css` 含 `--chat-primary` 明暗令牌与 `prefers-reduced-motion`
- `/brand.js` 定义 `BRAND.name === "Li&Chat"` 与 slogan
- `/theme.js` 含 `chat-theme`
- `/favicon.svg` 200、image/svg+xml
- `/ambient.js` 含 reduced-motion 分支与 canvas 创建
- `index.html` 含 favicon 链接、明暗 `theme-color`、首帧主题脚本

视觉验收：本地起服后用浏览器截图检查 375/1440 两档 × 明暗两种，重点看对比度、焦点环、氛围层与暗色无闪烁。

## 11. 验收标准

- 模板第 6 章 Pre-Delivery Checklist 与动效专项验收全部勾选
- `uv run pytest -q`、`uv run ruff check .`、`uv run mypy app` 全绿
- 既有后端契约（登录/登出/WS/CSRF）回归通过

## 12. 治理

代码事实（`style.css` / `brand.js`）优先于文档；实现完成后把最终令牌、组件、页面模式回写 `design-system/chat/MASTER.md`，决策与偏离理由回写 `BRAND.md`。本次允许的偏离：主色按产品域改为信使蓝（模板 §3.1 流程）、暂不引入标题字体、Logo 用 SVG 而非 WebP（模板 §3.2 允许内联 SVG 图标体系）。
