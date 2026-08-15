# Li&Chat UI 重构实施计划（设计模板首次实例化）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 Li-Design 模板把 Li&Chat 的 static/ 前端重构为带令牌、明暗主题、品牌氛围层与无障碍的成品 UI。

**Architecture:** 原生静态页零构建。`style.css` 持有 `--chat-*` 明暗令牌与组件类；`brand.js` 是品牌文案/Logo 单点；`theme.js` 管 `chat-theme` 与 `html.dark`；`ambient.js` 用 Canvas 画背景呼吸层；`app.js` 渲染 AuthShell/AppShell 并保持既有后端契约。

**Tech Stack:** 原生 HTML/CSS/JS；后端契约不变（FastAPI 同源托管，/api/me、/oidc/*、/ws）；测试 pytest + httpx ASGITransport；质量门禁 ruff + mypy。

## Global Constraints

- Python 3.12（uv 管理）；测试零外网（ASGITransport + 模拟 IdP），不监听端口
- 前端零构建、零第三方依赖、零远程字体；未来 CSP `style-src 'self'`（无 unsafe-inline）
- 命名：显示名 `Li&Chat`；CSS 令牌前缀 `chat`；主题存储键 `chat-theme`；基础设施标识 `lichat`
- 单一事实来源：颜色/阴影/动效只在 `static/style.css`；品牌文案/Logo 只在 `static/brand.js`；组件与 JS 禁止硬编码 hex 与文案
- 动效只动 `transform/opacity`；`prefers-reduced-motion` 全部单帧；移动端（<768px）氛围元素 ≤6
- 对比度：正文 ≥4.5:1；焦点环 2px 主色 + 2px offset；可点击目标 ≥44px
- 既有契约不得破坏：`/api/me`、`GET /oidc/login`、`POST /oidc/logout`（csrf_token）、WS 4401 关闭并跳登录、25 秒心跳
- 分支 `codex/ui-rebrand`；每个 Task 独立提交；Task 结束 `uv run pytest -q` + `uv run ruff check .` + `uv run mypy app` 全绿

---

## Task 1: 品牌令牌基座、品牌单点与主题脚本

**Files:**

- Create: `static/style.css`
- Create: `static/brand.js`
- Create: `static/theme.js`
- Create: `static/favicon.svg`
- Create: `design-system/chat/BRAND.md`
- Create: `design-system/chat/MASTER.md`
- Test: `tests/test_frontend.py`

**Interfaces:**

- Consumes: 无（绿地）
- Produces:
  - CSS 变量：`--chat-bg/surface/surface-2/fg/muted/border`、`--chat-primary/-hover/-soft/-fg`、`--chat-success/-warning/-destructive` 及 soft、`--chat-ring`（:root 与 .dark 两套）、`--shadow-sm/md/lg`、`--ease-out/--ease-spring`、`--motion-fast/base/slow`
  - 组件类：`.btn(.btn-primary/-secondary/-ghost/-danger/-link/-sm)`、`.card/.card-interactive`、`.badge-*`、`.notice-*`、`.label/.input`、`.spinner`、`.page-enter`、`.status-dot(.status-* )`、`.icon-btn/.theme-toggle`、`.ambient-layer`、外壳类 `.auth-shell/.app-shell/.auth-brand/.auth-card/.app-header/.app-main/.site-footer`
  - `window.BRAND`：`{ name, slug, slogan, description, icp, police, logo, footer() }`
  - `window.LiChatTheme`：`{ THEME_KEY, applyTheme(theme), initTheme() }`

- [ ] **Step 1: 开分支**

```bash
git switch -c codex/ui-rebrand
```

- [ ] **Step 2: 写失败测试**（扩展 `tests/test_frontend.py`，追加以下 4 个测试）

```python
async def test_style_has_brand_tokens(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/style.css")
    assert response.status_code == 200
    assert "--chat-primary: #2563eb" in response.text
    assert "--chat-primary: #60a5fa" in response.text
    assert "prefers-reduced-motion" in response.text


async def test_brand_single_source(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/brand.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert 'name: "Li&Chat"' in response.text
    assert "一次登录，直连你的小圈子" in response.text
    assert 'icp: ""' in response.text


async def test_theme_script(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/theme.js")
    assert response.status_code == 200
    assert "chat-theme" in response.text
    assert "classList.toggle" in response.text


async def test_favicon_served(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/favicon.svg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]
    assert "<svg" in response.text
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_frontend.py -v`
Expected: 新增 4 项 FAIL（404 Not Found）

- [ ] **Step 4: 最小实现 `static/style.css`**

```css
/* Li&Chat 品牌令牌与组件（首次设计实例化，源：design-system/template/reusable-tokens.template.css） */

:root {
  color-scheme: light;
  --chat-bg: #f8fafc;
  --chat-surface: #ffffff;
  --chat-surface-2: #f1f5f9;
  --chat-fg: #0f172a;
  --chat-muted: #64748b;
  --chat-border: #e2e8f0;
  --chat-primary: #2563eb;
  --chat-primary-hover: #1d4ed8;
  --chat-primary-soft: #dbeafe;
  --chat-primary-fg: #ffffff;
  --chat-success: #15803d;
  --chat-success-soft: #f0fdf4;
  --chat-warning: #b45309;
  --chat-warning-soft: #fffbeb;
  --chat-destructive: #dc2626;
  --chat-destructive-soft: #fef2f2;
  --chat-destructive-fg: #ffffff;
  --chat-ring: #2563eb;
  --shadow-sm: 0 0.6px 1.8px rgba(15, 23, 42, 0.02), 0 2.4px 7.2px rgba(15, 23, 42, 0.04);
  --shadow-md: 0 0.6px 1.8px rgba(15, 23, 42, 0.02), 0 2.4px 7.2px rgba(15, 23, 42, 0.04),
    0 8px 24px rgba(15, 23, 42, 0.06);
  --shadow-lg: 0 0.6px 1.8px rgba(15, 23, 42, 0.02), 0 2.4px 7.2px rgba(15, 23, 42, 0.04),
    0 8px 32px rgba(15, 23, 42, 0.08);
  --ease-out: cubic-bezier(0.25, 0.1, 0.25, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --motion-fast: 150ms;
  --motion-base: 250ms;
  --motion-slow: 350ms;
}

.dark {
  color-scheme: dark;
  --chat-bg: #0b1220;
  --chat-surface: #111a2c;
  --chat-surface-2: #1b2740;
  --chat-fg: #e2e8f0;
  --chat-muted: #94a3b8;
  --chat-border: #263449;
  --chat-primary: #60a5fa;
  --chat-primary-hover: #93c5fd;
  --chat-primary-soft: rgba(96, 165, 250, 0.14);
  --chat-primary-fg: #172554;
  --chat-success: #4ade80;
  --chat-success-soft: rgba(74, 222, 128, 0.12);
  --chat-warning: #fbbf24;
  --chat-warning-soft: rgba(251, 191, 36, 0.12);
  --chat-destructive: #f87171;
  --chat-destructive-soft: rgba(248, 113, 113, 0.12);
  --chat-destructive-fg: #450a0a;
  --chat-ring: #60a5fa;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--chat-bg);
  color: var(--chat-fg);
  font-family: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, "Noto Sans", "PingFang SC", "Hiragino Sans GB",
    "Microsoft YaHei", sans-serif;
  -webkit-font-smoothing: antialiased;
  transition: background-color var(--motion-base) var(--ease-out);
}

::selection {
  background: var(--chat-primary);
  color: var(--chat-primary-fg);
}

:focus-visible {
  outline: 2px solid var(--chat-ring);
  outline-offset: 2px;
  border-radius: 4px;
}

a {
  color: var(--chat-primary);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}

#app {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.auth-shell {
  align-items: center;
  justify-content: center;
  padding: 96px 16px 32px;
  text-align: center;
}

.auth-shell .theme-toggle {
  position: absolute;
  top: 16px;
  right: 16px;
}

.auth-brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.auth-brand .logo {
  height: 40px;
  width: 40px;
  color: var(--chat-primary);
}

.brand-name {
  font-size: 1.5rem;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.slogan {
  margin: 0 0 28px;
  color: var(--chat-muted);
  font-size: 0.95rem;
}

.auth-card {
  width: min(420px, 92vw);
  padding: 32px 28px;
  text-align: center;
}

.auth-card h1 {
  margin: 0 0 8px;
  font-size: 1.375rem;
}

.auth-card .muted {
  margin: 0 0 20px;
  color: var(--chat-muted);
  font-size: 0.9rem;
  line-height: 1.6;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--chat-border);
  background: var(--chat-bg);
}

.app-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.app-brand .logo {
  height: 28px;
  width: 28px;
  color: var(--chat-primary);
}

.app-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-main {
  flex: 1;
  width: min(1024px, calc(100% - 32px));
  margin: 24px auto 0;
}

.site-footer {
  margin-top: auto;
  padding: 40px 16px 16px;
  color: var(--chat-muted);
  font-size: 0.8rem;
  text-align: center;
}

.card {
  border: 1px solid var(--chat-border);
  border-radius: 16px;
  background: var(--chat-surface);
  box-shadow: var(--shadow-sm);
  transition:
    transform var(--motion-base) var(--ease-out),
    box-shadow var(--motion-base) var(--ease-out);
}

.card-interactive:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
}

.btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 44px;
  padding: 10px 18px;
  border: 1px solid transparent;
  border-radius: 8px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 500;
  line-height: 1;
  text-decoration: none;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition:
    color var(--motion-fast) var(--ease-out),
    background-color var(--motion-fast) var(--ease-out),
    border-color var(--motion-fast) var(--ease-out),
    box-shadow var(--motion-fast) var(--ease-out),
    transform var(--motion-base) var(--ease-spring);
}

.btn:disabled {
  pointer-events: none;
  opacity: 0.5;
}

.btn:not(:disabled):hover {
  transform: translateY(-1px);
}

.btn:not(:disabled):active {
  transform: translateY(0) scale(0.97);
}

.btn-primary {
  color: var(--chat-primary-fg);
  background-image: linear-gradient(180deg, var(--chat-primary), var(--chat-primary-hover));
  background-size: 100% 200%;
  background-position: 50% 0;
  box-shadow: var(--shadow-sm);
}

.btn-primary:not(:disabled):hover {
  background-position: 50% 100%;
  box-shadow: var(--shadow-md);
}

.btn-secondary {
  border-color: var(--chat-border);
  background: var(--chat-surface);
  color: var(--chat-fg);
}

.btn-secondary:not(:disabled):hover {
  background: var(--chat-surface-2);
}

.btn-ghost {
  color: var(--chat-muted);
}

.btn-ghost:not(:disabled):hover {
  background: var(--chat-surface-2);
  color: var(--chat-fg);
}

.btn-danger {
  color: var(--chat-destructive-fg);
  background: var(--chat-destructive);
  box-shadow: var(--shadow-sm);
}

.btn-danger:not(:disabled):hover {
  opacity: 0.9;
}

.btn-link {
  min-height: auto;
  padding: 0;
  color: var(--chat-primary);
}

.btn-link:hover {
  text-decoration: underline;
}

.btn-sm {
  min-height: 36px;
  padding: 8px 14px;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 44px;
  width: 44px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: var(--chat-surface);
  color: var(--chat-muted);
  cursor: pointer;
  transition:
    color var(--motion-fast) var(--ease-out),
    background-color var(--motion-fast) var(--ease-out);
}

.icon-btn:hover {
  color: var(--chat-fg);
  background: var(--chat-surface-2);
}

.icon-btn svg {
  height: 20px;
  width: 20px;
}

.icon-moon {
  display: none;
}

.dark .icon-sun {
  display: none;
}

.dark .icon-moon {
  display: block;
}

.label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.875rem;
  font-weight: 500;
}

.input {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: var(--chat-surface);
  color: var(--chat-fg);
  font: inherit;
  font-size: 0.9rem;
  box-shadow: var(--shadow-sm);
}

.input::placeholder {
  color: var(--chat-muted);
}

.input:focus {
  border-color: var(--chat-primary);
  outline: none;
  box-shadow: 0 0 0 3px var(--chat-primary-soft);
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
  white-space: nowrap;
}

.badge-success {
  background: var(--chat-success-soft);
  color: var(--chat-success);
}

.badge-warning {
  background: var(--chat-warning-soft);
  color: var(--chat-warning);
}

.badge-danger {
  background: var(--chat-destructive-soft);
  color: var(--chat-destructive);
}

.badge-muted {
  background: var(--chat-surface-2);
  color: var(--chat-muted);
}

.badge-primary {
  background: var(--chat-primary-soft);
  color: var(--chat-primary);
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  font-size: 0.875rem;
  line-height: 1.5;
}

.me-card {
  width: min(560px, 100%);
  margin: 0 auto;
  padding: 32px 28px;
  text-align: center;
}

.me {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-bottom: 18px;
}

.avatar {
  height: 56px;
  width: 56px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--chat-surface-2);
}

.avatar-placeholder {
  display: grid;
  place-items: center;
  background: var(--chat-primary);
  color: var(--chat-primary-fg);
  font-size: 1.4rem;
  font-weight: 600;
}

.nickname {
  font-size: 1.15rem;
  font-weight: 600;
}

.ws-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--chat-muted);
  font-size: 0.85rem;
}

.status-dot {
  height: 8px;
  width: 8px;
  border-radius: 50%;
  background: var(--chat-muted);
}

.status-connecting {
  background: var(--chat-warning);
}

.status-connected {
  background: var(--chat-success);
}

.status-disconnected {
  background: var(--chat-muted);
}

.status-invalid {
  background: var(--chat-destructive);
}

.page-enter {
  animation: page-fade-up var(--motion-slow) var(--ease-out) both;
}

@keyframes page-fade-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.spinner {
  display: inline-block;
  height: 1rem;
  width: 1rem;
  border-radius: 50%;
  border: 2px solid currentColor;
  border-top-color: transparent;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.ambient-layer {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

@media (max-width: 768px) {
  .auth-card {
    padding: 24px 20px;
  }
  .app-main {
    width: 100%;
    margin-top: 16px;
    padding: 0 12px;
  }
}

@media (max-width: 480px) {
  .brand-name {
    font-size: 1.25rem;
  }
}
```

- [ ] **Step 5: 最小实现 `static/brand.js`**

```js
"use strict";

/* 品牌单点：名称 / slogan / Logo / 备案的唯一出处（等价于模板中的 brand.ts）。 */

const LOGO_MARK = `<svg class="logo" viewBox="0 0 48 48" fill="none" aria-hidden="true">
  <rect x="5" y="17" width="18" height="18" rx="5" stroke="currentColor" stroke-width="2.5"/>
  <path d="M23 23 29 15" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
  <rect x="26" y="8" width="17" height="17" rx="5" stroke="currentColor" stroke-width="2.5"/>
  <circle cx="34.5" cy="16.5" r="2.25" fill="currentColor" stroke="none"/>
</svg>`;

window.BRAND = Object.freeze({
  name: "Li&Chat",
  slug: "chat",
  slogan: "一次登录，直连你的小圈子",
  description: "Li&Chat——一次登录，直连你的小圈子",
  icp: "",
  police: "",
  logo: LOGO_MARK,
  footer: function () {
    const parts = [this.name, this.slogan];
    if (this.icp) parts.push(this.icp);
    if (this.police) parts.push(this.police);
    return parts.join(" · ");
  },
});
```

- [ ] **Step 6: 最小实现 `static/theme.js`**

```js
"use strict";

const THEME_KEY = "chat-theme";
const DARK_BG = "#0b1220";
const LIGHT_BG = "#f8fafc";

function systemPrefersDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(theme) {
  const dark = theme === "dark" || (theme !== "light" && systemPrefersDark());
  document.documentElement.classList.toggle("dark", dark);
  return dark ? "dark" : "light";
}

function syncThemeColor(dark) {
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.removeAttribute("media");
    meta.setAttribute("content", dark ? DARK_BG : LIGHT_BG);
  });
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem(THEME_KEY);
  } catch {
    saved = null;
  }
  const current = applyTheme(saved);
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;
  toggle.setAttribute("aria-label", current === "dark" ? "切换到浅色模式" : "切换到深色模式");
  toggle.addEventListener("click", () => {
    const next = document.documentElement.classList.contains("dark") ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* 隐私模式下忽略 */
    }
    applyTheme(next);
    syncThemeColor(next === "dark");
    toggle.setAttribute("aria-label", next === "dark" ? "切换到浅色模式" : "切换到深色模式");
  });
}

window.LiChatTheme = { THEME_KEY, applyTheme, initTheme };
```

- [ ] **Step 7: 最小实现 `static/favicon.svg`**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none">
  <rect x="5" y="17" width="18" height="18" rx="5" stroke="#2563eb" stroke-width="3"/>
  <path d="M23 23 29 15" stroke="#2563eb" stroke-width="3" stroke-linecap="round"/>
  <rect x="26" y="8" width="17" height="17" rx="5" stroke="#2563eb" stroke-width="3"/>
  <circle cx="34.5" cy="16.5" r="2.75" fill="#2563eb"/>
</svg>
```

- [ ] **Step 8: 写 `design-system/chat/BRAND.md`**

```markdown
# Li&Chat · 品牌 UI 设计报告

> **版本**：V1.0 ｜ **日期**：2026-08-16 ｜ **状态**：已发布（后续统一风格以本文件为准）
> **适用范围**：static/ 全部前端界面（登录外壳、登录后外壳）。
> **配套文档**：实现速览见 [MASTER.md](./MASTER.md)；代码事实以 `static/style.css` 令牌与 `static/brand.js` 为准。

## 1. 品牌定位与人格

| 维度 | 描述 |
| --- | --- |
| 一句话定位 | 一次登录，直连你的小圈子 |
| 人格关键词 | 可信、克制、安静、流畅、私密 |
| 人格比喻 | 可靠的信使：准确送达、不多嘴、不打扰 |
| 品牌承诺 | 对话只在你们之间流动；每一次登录都经 Li&Pass 验证 |
| 避免成为 | 嘈杂的社交广场、冷冰冰的聊天工具、花哨的营销页 |

## 2. 五大设计原则（TRUST 内核，继承不变层）

1. 信任优先：色彩、字体、徽章、文案传递「安全但不唬人」。
2. 克制的科技感：中性底色 + 单一主色强调，不用渐变霓虹与 AI 紫粉。
3. 以动衬静：入场动效一次性打招呼，环境动效极慢极淡、只动 transform/opacity、尊重 prefers-reduced-motion。
4. 单一事实来源：令牌只在 style.css，品牌文案与 Logo 只在 brand.js，组件禁止硬编码。
5. 无障碍与节能：对比度 ≥4.5:1、焦点可见、可点击 ≥44px、移动端减量省电。

## 3. 视觉识别规范

### 3.1 色彩系统

主色 = 信使蓝 `#2563EB`（浅）/ `#60A5FA`（深），按 ui-ux-pro-max 规则库「Chat & Messaging App」首选确定（见设计规格 §3）。

浅色：bg `#F8FAFC` / surface `#FFFFFF` / surface-2 `#F1F5F9` / fg `#0F172A` / muted `#64748B` / border `#E2E8F0`；primary `#2563EB` hover `#1D4ED8` soft `#DBEAFE` fg `#FFFFFF`；success `#15803D` / warning `#B45309` / destructive `#DC2626` 及 soft；ring `#2563EB`。

深色：bg `#0B1220` / surface `#111A2C` / surface-2 `#1B2740` / fg `#E2E8F0` / muted `#94A3B8` / border `#263449`；primary `#60A5FA` hover `#93C5FD` soft `rgba(96,165,250,0.14)` fg `#172554`；success `#4ADE80` / warning `#FBBF24` / destructive `#F87171`；ring `#60A5FA`。

用色比例 60/30/10；主色永远小面积强调；语义色只表达状态。

### 3.2 字体与排版

字体栈 Inter → 系统栈 → PingFang SC / 微软雅黑，不加载远程字体；正文 16px/1.5；暂不引入标题字体（零外部依赖，后续如需要自托管 subset）。

### 3.3 形状、间距与层次

按钮/输入框 8px 圆角，卡片 16px，徽章 999px；间距 4px 刻度，卡片内边距 24px 起步；三档弥散阴影透明度总和 <0.1；层级：氛围层 z-0 < 内容 z-1 < 顶栏 z-20。

### 3.4 Logo 与图标

Logo 为家族几何语法 SVG 标识「两个方块以细线相连、右上方带光斑」（对话 + 在线），单源定义于 brand.js，favicon 用同形 SVG；图标一律内联 SVG（24 viewBox、2px 描边、圆角端点、currentColor），禁止 emoji。

## 4. 氛围动效（呼吸感四模式）

符号隐喻：直线=消息通路、Z 形=对话往返、方块=消息、光斑=在线状态；锁钥仅在信任关键时刻出现，不在背景层使用。

浓度：登录页 10、登录后 8；移动端（<768px）≤6 且更慢更淡；prefers-reduced-motion 下绘制静态单帧；元素 pointer-events:none、永远在内容层之下。

## 5. 文案语调

清晰优先、动词开头按钮、不用感叹号、错误可行动、安全语言诚实但不吓唬、数字与时间精确。

## 6. 治理

四级分层：BRAND.md（意图）→ MASTER.md（快照）→ style.css / brand.js（代码事实）→ 页面。冲突时以代码为准并回写文档。

## 7. 槽位表

（与设计规格 §4 一致，含 1–20 项：显示名、技术标识、定位、承诺、人格、符号隐喻、主色明暗、中性色明暗、语义色、焦点环、字体栈、标题字体、Logo、前缀 `chat`、主题键 `chat-theme`、slogan/备案、氛围浓度、浏览器品牌位。）
```

- [ ] **Step 9: 写 `design-system/chat/MASTER.md` 初稿**

```markdown
# Li&Chat 设计系统实现速览（MASTER）

> 状态：随代码回写 ｜ 代码事实：static/style.css、static/brand.js

## 令牌快照

（浅/深两套与 style.css 完全一致：--chat-bg/surface/surface-2/fg/muted/border、primary 四件套、success/warning/destructive、ring、shadow-sm/md/lg、ease-out/ease-spring、motion-fast/base/slow。）

## 组件清单

| 类名 | 用途 |
| --- | --- |
| .btn-* | primary/secondary/ghost/danger/link，按压 scale(0.97)、hover 上移 1px |
| .card / .card-interactive | 16px 圆角表面 + 弥散阴影；interactive hover 上移 |
| .badge-* | 语义状态徽章（success/warning/danger/muted/primary） |
| .label / .input | 表单（预留，里程碑二使用） |
| .notice | 提示条 |
| .status-dot | 在线状态：connecting/connected/disconnected/invalid |
| .icon-btn / .theme-toggle | 44px 图标按钮；明暗图标随 .dark 切换 |
| .spinner / .page-enter | 加载与入场 |
| .ambient-layer | Canvas 氛围层容器 |

## 页面模式

AuthShell：居中 max-w-md 卡片（品牌标识 + slogan + 登录卡 + 底部备案）；AppShell：sticky 顶栏 + max-w-5xl 内容 + 底部备案。

## 品牌单点

brand.js 暴露 `BRAND.{name,slug,slogan,description,icp,police,logo,footer()}`；页面禁止硬编码文案。

## 氛围层

ambient.js 暴露 `LiChatAmbient.setDensity(n)`；浓度：登录 10、登录后 8、移动端 ≤6；reduced-motion 单帧。

## 验收状态

Pre-Delivery Checklist 在收尾 Task 回写。
```

- [ ] **Step 10: 运行确认通过**

Run: `uv run pytest tests/test_frontend.py -v`
Expected: 全部 PASS

- [ ] **Step 11: 全量门禁与提交**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy app
git add static/style.css static/brand.js static/theme.js static/favicon.svg design-system/chat/BRAND.md design-system/chat/MASTER.md tests/test_frontend.py
git commit -m "feat(ui): 品牌令牌基座、品牌单点与主题脚本"
```

---

## Task 2: 页面外壳、浏览器品牌位与无障碍

**Files:**

- Modify: `static/index.html`
- Modify: `static/app.js`
- Test: `tests/test_frontend.py`

**Interfaces:**

- Consumes: `BRAND.logo/name/slogan/footer()`、`LiChatTheme.initTheme()`（Task 1）
- Produces:
  - `#app` 外壳：`.auth-shell`（未登录）/`.app-shell`（已登录），`mount(className, innerHtml)` 内部函数
  - `#theme-toggle` 按钮存在于两种外壳；`#ws-dot`（`.status-dot.status-*`）与 `#ws-text`（`role="status"`）
  - 保持契约：`/api/me`、`GET /oidc/login`、`POST /oidc/logout`（hidden `csrf_token`）、WS 4401 → `/oidc/login`、25 秒 ping

- [ ] **Step 1: 写失败测试**（追加以下 2 个测试）

```python
async def test_index_brand_chrome(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/")
    assert response.status_code == 200
    text = response.text
    assert 'rel="icon"' in text
    assert 'href="/favicon.svg"' in text
    assert 'name="theme-color"' in text
    assert "chat-theme" in text
    assert 'src="/brand.js"' in text
    assert 'src="/theme.js"' in text
    assert 'src="/ambient.js"' in text


async def test_app_script_contracts(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    text = response.text
    assert 'href="/oidc/login"' in text
    assert "csrf_token" in text
    assert "4401" in text
    assert 'role="status"' in text
    assert "LiChatTheme.initTheme" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_frontend.py -v`
Expected: `test_index_brand_chrome`、`test_app_script_contracts` FAIL

- [ ] **Step 3: 实现 `static/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Li&Chat</title>
    <meta name="description" content="Li&Chat——一次登录，直连你的小圈子" />
    <meta name="theme-color" content="#f8fafc" media="(prefers-color-scheme: light)" />
    <meta name="theme-color" content="#0b1220" media="(prefers-color-scheme: dark)" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="stylesheet" href="/style.css" />
    <script>
      (function () {
        try {
          var saved = localStorage.getItem("chat-theme");
          var dark =
            saved === "dark" ||
            (saved !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
          document.documentElement.classList.toggle("dark", dark);
        } catch (e) {}
      })();
    </script>
  </head>
  <body>
    <main id="app" class="auth-shell" aria-live="polite">
      <noscript>Li&Chat 需要启用 JavaScript。</noscript>
    </main>
    <script src="/brand.js" defer></script>
    <script src="/theme.js" defer></script>
    <script src="/ambient.js" defer></script>
    <script src="/app.js" defer></script>
  </body>
</html>
```

- [ ] **Step 4: 实现 `static/app.js`**

```js
"use strict";

const state = { me: null, ws: null, pingTimer: null };

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function footerHtml() {
  return `<footer class="site-footer">${escapeHtml(BRAND.footer())}</footer>`;
}

function themeToggleHtml() {
  return `
    <button id="theme-toggle" class="icon-btn theme-toggle" type="button" aria-label="切换主题">
      <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" aria-hidden="true">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
      </svg>
      <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    </button>`;
}

function mount(className, inner) {
  const app = document.getElementById("app");
  app.className = className;
  app.innerHTML = inner;
  LiChatTheme.initTheme();
}

async function loadMe() {
  let response;
  try {
    response = await fetch("/api/me", { credentials: "same-origin" });
  } catch {
    renderLoggedOut();
    return;
  }
  if (!response.ok) {
    renderLoggedOut();
    return;
  }
  state.me = await response.json();
  renderLoggedIn();
  connectWebSocket();
}

function renderLoggedOut() {
  window.LiChatAmbient && window.LiChatAmbient.setDensity(10);
  mount(
    "auth-shell",
    `${themeToggleHtml()}
    <div class="auth-brand">${BRAND.logo}<span class="brand-name">${escapeHtml(BRAND.name)}</span></div>
    <p class="slogan">${escapeHtml(BRAND.slogan)}</p>
    <section class="card card-interactive auth-card page-enter">
      <h1>欢迎回来</h1>
      <p class="muted">统一使用 Li&Pass 账号登录，本地不保存密码。</p>
      <a class="btn btn-primary" href="/oidc/login">使用 Li&Pass 登录</a>
    </section>
    ${footerHtml()}`
  );
}

function renderLoggedIn() {
  const me = state.me;
  const displayName = me.nickname || me.name || me.sub;
  const avatar = me.picture
    ? `<img class="avatar" src="${escapeHtml(me.picture)}" alt="头像" />`
    : `<div class="avatar avatar-placeholder" aria-hidden="true">${escapeHtml(
        displayName.slice(0, 1).toUpperCase()
      )}</div>`;
  window.LiChatAmbient && window.LiChatAmbient.setDensity(8);
  mount(
    "app-shell",
    `<header class="app-header">
      <div class="app-brand">${BRAND.logo}<span>${escapeHtml(BRAND.name)}</span></div>
      <div class="app-actions">
        ${themeToggleHtml()}
        <button id="logout" class="btn btn-secondary btn-sm" type="button">退出登录</button>
      </div>
    </header>
    <main class="app-main">
      <section class="card me-card page-enter">
        <div class="me">
          ${avatar}
          <span class="nickname">${escapeHtml(displayName)}</span>
        </div>
        <div class="ws-status">
          <span id="ws-dot" class="status-dot status-connecting" aria-hidden="true"></span>
          <span id="ws-text" role="status">连接中…</span>
        </div>
      </section>
    </main>
    ${footerHtml()}`
  );
  document.getElementById("logout").addEventListener("click", logout);
}

function logout() {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/oidc/logout";
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = "csrf_token";
  input.value = state.me.csrf_token;
  form.appendChild(input);
  document.body.appendChild(form);
  form.submit();
}

function connectWebSocket() {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${window.location.host}/ws`);
  state.ws = socket;

  function setStatus(kind, text) {
    const dot = document.getElementById("ws-dot");
    const label = document.getElementById("ws-text");
    if (dot) dot.className = `status-dot status-${kind}`;
    if (label) label.textContent = text;
  }

  socket.addEventListener("open", () => setStatus("connected", "已连接"));
  socket.addEventListener("error", () => setStatus("disconnected", "连接已断开"));
  socket.addEventListener("close", (event) => {
    if (event.code === 4401) {
      setStatus("invalid", "登录已失效，正在跳转…");
      window.location.href = "/oidc/login";
      return;
    }
    setStatus("disconnected", "连接已断开");
  });

  state.pingTimer = window.setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, 25000);
}

loadMe();
```

- [ ] **Step 5: 运行确认通过**

Run: `uv run pytest tests/test_frontend.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 全量门禁与提交**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy app
git add static/index.html static/app.js tests/test_frontend.py
git commit -m "feat(ui): AuthShell/AppShell 外壳、浏览器品牌位与无障碍"
```

---

## Task 3: Canvas 环境呼吸层

**Files:**

- Create: `static/ambient.js`
- Test: `tests/test_frontend.py`

**Interfaces:**

- Consumes: CSS 变量 `--chat-primary/-border/-muted`（getComputedStyle 读取）、`#app` 外壳类名判断初始浓度（Task 1/2）
- Produces: `window.LiChatAmbient = { setDensity(n) }`；自动创建 `canvas.ambient-layer` 并追加到 body

- [ ] **Step 1: 写失败测试**

```python
async def test_ambient_script(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/ambient.js")
    assert response.status_code == 200
    assert "canvas" in response.text
    assert "prefers-reduced-motion" in response.text
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_frontend.py::test_ambient_script -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现 `static/ambient.js`**

```js
"use strict";

/* 环境呼吸层：Canvas 版 FloatingBackground（无第三方依赖）。
   只画在背景层、pointer-events:none；reduced-motion 下仅绘制静态单帧。 */

(function () {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const mobileQuery = window.matchMedia("(max-width: 768px)");

  const canvas = document.createElement("canvas");
  canvas.className = "ambient-layer";
  canvas.setAttribute("aria-hidden", "true");
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");

  let width = 0;
  let height = 0;
  let rafId = 0;
  let frameCount = 0;
  let shapes = [];
  let colors = { primary: "#2563eb", border: "#e2e8f0", muted: "#64748b" };
  let density = (document.getElementById("app") || {}).className.includes("auth-shell") ? 10 : 8;

  function readColors() {
    const css = getComputedStyle(document.documentElement);
    colors = {
      primary: css.getPropertyValue("--chat-primary").trim(),
      border: css.getPropertyValue("--chat-border").trim(),
      muted: css.getPropertyValue("--chat-muted").trim(),
    };
  }

  function buildShapes() {
    const cap = mobileQuery.matches ? Math.min(6, density) : density;
    const kinds = ["line", "square", "z", "dot"];
    shapes = [];
    for (let i = 0; i < cap; i += 1) {
      const size = 14 + ((i * 17) % 42);
      shapes.push({
        kind: kinds[i % kinds.length],
        x: ((i + 1) / (cap + 1)) * width,
        y: 40 + ((i * 97) % Math.max(60, height - 80)),
        size,
        speed: mobileQuery.matches ? 6 + (i % 3) * 3 : 10 + (i % 4) * 6,
        phase: (i / cap) * Math.PI * 2 + ((i * 37) % 20) / 10,
        alpha: 0.04 + (i % 4) * 0.02,
      });
    }
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    buildShapes();
  }

  function drawShape(shape, t) {
    ctx.globalAlpha = shape.alpha;
    ctx.strokeStyle = colors.primary;
    ctx.fillStyle = colors.primary;
    ctx.lineWidth = 1.5;
    ctx.lineCap = "round";
    if (shape.kind === "square") {
      const x = shape.x + Math.sin(t * shape.speed * 0.004 + shape.phase) * 60;
      const y = shape.y + Math.sin(t * shape.speed * 0.002 + shape.phase) * 24;
      ctx.strokeRect(x, y, shape.size, shape.size);
    } else if (shape.kind === "line") {
      const x = ((t * shape.speed + shape.x) % (width + 240)) - 120;
      const y = shape.y + Math.sin(t * shape.speed * 0.003 + shape.phase) * 18;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + 90, y);
      ctx.stroke();
    } else if (shape.kind === "z") {
      const x = ((t * shape.speed * 0.7 + shape.x) % (width + 240)) - 120;
      const y = shape.y + Math.sin(t * shape.speed * 0.002 + shape.phase) * 14;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + 28, y);
      ctx.lineTo(x + 28, y + 18);
      ctx.lineTo(x + 56, y + 18);
      ctx.stroke();
    } else {
      const cx = width * (0.15 + ((shape.phase / (Math.PI * 2)) % 1) * 0.7);
      const cy = height * 0.45;
      const angle = t * shape.speed * 0.002 + shape.phase;
      ctx.beginPath();
      ctx.arc(cx + Math.cos(angle) * shape.size * 3, cy + Math.sin(angle) * shape.size, 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function frame(t) {
    frameCount += 1;
    if (frameCount % 60 === 0) readColors();
    ctx.clearRect(0, 0, width, height);
    for (const shape of shapes) drawShape(shape, t);
    rafId = window.requestAnimationFrame(frame);
  }

  function start() {
    readColors();
    resize();
    if (reduced) {
      frame(0);
      window.cancelAnimationFrame(rafId);
      return;
    }
    rafId = window.requestAnimationFrame(frame);
  }

  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      window.cancelAnimationFrame(rafId);
    } else if (!reduced) {
      rafId = window.requestAnimationFrame(frame);
    }
  });

  window.LiChatAmbient = {
    setDensity(value) {
      density = value;
      buildShapes();
    },
  };

  start();
})();
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_frontend.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 全量门禁与提交**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy app
git add static/ambient.js tests/test_frontend.py
git commit -m "feat(ui): Canvas 环境呼吸层"
```

---

## Task 4: 治理回写、视觉验收与合并

**Files:**

- Modify: `design-system/chat/MASTER.md`（回写最终值 + 验收状态）
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `AGENTS.md`（测试数量）

**Interfaces:**

- Consumes: Task 1–3 全部产出
- Produces: main 分支合并提交（保留 merge 记录）

- [ ] **Step 1: 全量门禁**

```bash
uv run pytest -q      # 期望 62 passed
uv run ruff check .
uv run mypy app
```

- [ ] **Step 2: 本地起服做视觉验收**（375px / 1440px × 浅色 / 深色截图，过模板第 6 章 Checklist）

```bash
uv run uvicorn app.main:app --port 8000
curl -fsS http://localhost:8000/healthz
```

检查项：无 emoji 图标、可点击元素 cursor-pointer、hover 150–300ms、对比度 ≥4.5:1、focus-visible 可见、reduced-motion 单帧、375/768/1024/1440 无横向滚动、暗色无闪烁、氛围层浓度与移动端 ≤6。

- [ ] **Step 3: 回写 `design-system/chat/MASTER.md`**（令牌/组件/页面/验收勾选为最终状态）

- [ ] **Step 4: 更新 `CHANGELOG.md`**（顶部新增「未发布（开发中）」分区：功能 + 文档）

- [ ] **Step 5: 更新 `README.md`**（项目结构补充 design-system/ 与 static/ 描述；文档索引补 BRAND/MASTER；测试数量改 62）

- [ ] **Step 6: 更新 `AGENTS.md`**（§三 static/tests 注释与 §七测试数量改 62）

- [ ] **Step 7: 提交并合并**

```bash
git add design-system/chat/MASTER.md CHANGELOG.md README.md AGENTS.md
git commit -m "docs: 品牌方案回写与 UI 重构收尾"
git switch main
git merge --no-ff codex/ui-rebrand -m "merge: UI 首次设计实例化（codex/ui-rebrand）"
```

## Self-Review 记录

- Spec 覆盖：§4 槽位 → Task 1（BRAND.md + 令牌）；§6 文件映射 → Task 1/2/3；§7 组件与外壳 → Task 1/2；§8 契约 → Task 2（含回归测试）；§9 无障碍 → Task 1/2 + Task 4 验收；§10 测试 → 各 Task Step；§11 验收 → Task 4；§12 治理 → Task 4 回写。
- 占位符：无（所有代码块为最终内容；MASTER.md 初稿在 Task 4 回写为最终状态，这是计划的明确步骤而非 TBD）。
- 类型一致：`BRAND.logo/name/slogan/footer()`、`LiChatTheme.initTheme()`、`LiChatAmbient.setDensity(n)` 在 Task 1 定义、Task 2/3 使用，签名一致。
