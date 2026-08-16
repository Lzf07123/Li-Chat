# Li&Chat 设计系统实现速览（MASTER）

> 状态：已回写（2026-08-16，随首次设计实例化） ｜ 代码事实：static/style.css、static/brand.js

## 令牌快照

浅色（`:root`）：bg `#F8FAFC` / surface `#FFFFFF` / surface-2 `#F1F5F9` / fg `#0F172A` / muted `#64748B` / border `#E2E8F0`；primary `#2563EB` hover `#1D4ED8` soft `#DBEAFE` fg `#FFFFFF`；success `#15803D` / warning `#B45309` / destructive `#DC2626` 及 soft；ring `#2563EB`。

深色（`.dark`）：bg `#0B1220` / surface `#111A2C` / surface-2 `#1B2740` / fg `#E2E8F0` / muted `#94A3B8` / border `#263449`；primary `#60A5FA` hover `#93C5FD` soft `rgba(96,165,250,0.14)` fg `#172554`；success `#4ADE80` / warning `#FBBF24` / destructive `#F87171`；ring `#60A5FA`。

阴影 `--shadow-sm/md/lg` 三档弥散（透明度总和 <0.1）；缓动 `--ease-out` / `--ease-spring`；时长 `--motion-fast/base/slow = 150/250/350ms`。

## 组件清单

| 类名 | 用途 |
| --- | --- |
| .btn-* | primary/secondary/ghost/danger/link/sm；按压 scale(0.97)、hover 上移 1px、disabled opacity-50 |
| .card / .card-interactive | 16px 圆角表面 + 弥散阴影；interactive hover 上移 |
| .badge-* | 语义状态徽章（success/warning/danger/muted/primary） |
| .label / .input | 表单（预留，里程碑二使用） |
| .notice | 提示条 |
| .status-dot | 在线状态：connecting/connected/disconnected/invalid |
| .icon-btn / .theme-toggle | 44px 图标按钮；明暗图标随 .dark 切换 |
| .spinner / .page-enter | 加载与入场 |
| .ambient-layer | Canvas 氛围层容器（z-0、pointer-events:none） |

## 页面模式

AuthShell（未登录）：居中 max-w-md 卡片（右上角主题切换 + 品牌标识 + slogan + 登录卡 + 底部
备案），登录外壳本身可内滚。

AppShell（已登录，微信式全高双栏）：`100dvh` 应用外壳、页面不滚动——顶部品牌栏（品牌 +
连接状态 + 个人菜单 + 主题切换）+ 双栏主区（会话列表栏 300px 内滚 + 聊天面板全高，消息列表
与输入框内部滚动，输入框固定在面板底部）+ 底部备案。整体 `max-width: 1200px`（紧凑密度
1160px）居中，消息/输入内容列 `max-width: 880px`（紧凑密度 840px）居中；移动端 <768px
单栏切换（列表 ↔ 聊天，返回按钮）、顶栏
与输入框适配 `env(safe-area-inset-*)`、隐藏页脚。品牌令牌（信使蓝、中性色、圆角/阴影）不变。

密度策略：桌面端（≥768px）走紧凑密度层——按钮/图标钮/头像/气泡/间距整体收紧；移动端
（<768px）恢复 44px 触控热区与更宽松的消息排版，保证可点击性与可读性不降级。

## 品牌单点

brand.js 暴露 `BRAND.{name,slug,slogan,description,icp,police,logo,footer()}`；页面禁止硬编码文案；Logo 为内联 SVG（两个方块细线相连 + 右侧光斑）。

## 氛围层

ambient.js 暴露 `LiChatAmbient.setDensity(n)`；浓度：登录 10、登录后 8、移动端（<768px）≤6；四类符号（直线穿行/方块钟摆/Z 形穿行/光斑公转）；颜色读 CSS 令牌；页面隐藏时暂停；reduced-motion 单帧。

## 验收状态

布局回归（2026-08-16，微信式布局）：桌面 1440×900 与移动 390×844 经无头浏览器程序化验收——
页面 `scrollY=0`、`body overflow:hidden`、无横向溢出、聊天框内部滚动（可见高度 < 内容高度）、
桌面主区 ≤1200px / 内容列 ≤880px、移动端列表↔聊天切换正常、输入框未越出视口。

紧凑密度回归（2026-08-16）：桌面按钮 30–36px、图标钮 34px、头像 30px、气泡 14.7px、
头部 53px；移动端保留 44px 热区、气泡 15.2px；页面不滚/内滚/无横向溢出复验通过。

Pre-Delivery Checklist 全部通过（2026-08-16）：无 emoji 图标、可点击元素 cursor-pointer、hover 150–300ms、正文对比度 ≥4.5:1、focus-visible 2px 主色描边、reduced-motion 单帧、375/1440 无横向滚动、令牌与文案无硬编码、明暗切换无闪烁（首帧内联脚本 + 像素抽样验证：浅 `#F8FAFC` / 深 `#0B1220`）。视觉基线见 [preview/](./preview/)。
