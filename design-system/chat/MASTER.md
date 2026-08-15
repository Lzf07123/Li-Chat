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
