# Li&Chat 设计系统实现速览（MASTER）

> 状态：已回写（2026-08-16 首次实例化；2026-08-17 同步模板 V1.2 并全量采纳海玻璃配色） ｜ 代码事实：static/style.css、static/brand.js

## 令牌快照

浅色（`:root`）：bg `#F6FBF9` / surface `#FFFFFF` / surface-2 `#EEF6F3` / fg `#35423F` / muted `#64736C` / border `#E1ECE8`；primary `#25786D` hover `#1F6359` soft `#D9F4EE` fg `#FFFFFF`；secondary `#2F678F` / soft `#DFF1FA`；success `#2A7C52` / warning `#9A5C05` / destructive `#C43737` 及 soft；ring `#25786D`。

深色（`.dark`，D1 雾灰）：bg `#3A3F45` / surface `#434950` / surface-2 `#4B5259` / fg `#F0F2F4` / muted `#B8C0C7` / border `#545C64`；primary `#7FD4C6` hover `#A5E4D9` soft `rgba(127,212,198,0.16)` fg `#17332E`；secondary `#A8D4F0` / soft `rgba(168,212,240,0.16)`；success `#86D6AC` / warning `#EAD48E` / destructive `#E8A49A`；ring `#7FD4C6`。

阴影 `--shadow-sm/md/lg` 三档水绿 tint 弥散（透明度总和 <0.1）；缓动 `--ease-out` / `--ease-spring`；时长 `--motion-fast/base/slow = 150/250/350ms`。

强调色板（V1.2）：ice/aqua/lilac/sage/mint/sand 六色相 strong+soft 明暗两套令牌已落地，
暂未接装饰位（合计 ≤15% 可视面积铁律）。

按钮着色（V1.2）：`--chat-btn-primary-bg/-bg-hover/-border`（浅 `rgba(47,127,116,.10/.17/.26)`、
深 `rgba(127,212,198,.13/.21/.30)`）、`--chat-brand-fg`（浅 `#24433E`、深 `#D7EFEA`）、
`--chat-btn-sweep`（扫光亮度，浅 `.42` / 深 `.18`）。

深色软底（模板附录 E）：`--chat-*-soft-solid/-soft-fg` 实色粉彩底 + 深字（primary
`#D9F4EE`/`#17332E`、success `#E3F6E9`/`#14532D`、warning `#FDF3D8`/`#78350F`、
destructive `#FDEEEE`/`#7F1D1D`）；带文字的软底组件经 fallback 引用，图标/图形仍可用 rgba 软底。

## 组件清单

| 类名 | 用途 |
| --- | --- |
| .btn-* | primary/secondary/ghost/danger/link/sm；主按钮半透明单色着色 + 细描边 + `::after` 扫光（4s，disabled 关闭）；按压 scale(0.97)、hover 上移 1px、disabled opacity-50 |
| .card / .card-interactive | 16px 圆角表面 + 弥散阴影；interactive hover 上移 |
| .auth-halo / .auth-brand::before | 认证卡与 Logo 呼吸辉光（4.5s，reduced-motion 静止） |
| .badge-* | 语义状态徽章（success/warning/danger/muted/primary） |
| .label / .input | 表单（预留，里程碑二使用） |
| .notice | 提示条 |
| .status-dot | 在线状态：connecting/connected/disconnected/invalid |
| .icon-btn / .theme-toggle | 44px 图标按钮；明暗图标随 .dark 切换 |
| .spinner / .page-enter | 加载与入场 |
| .ambient-layer | Canvas 氛围层容器（z-0、pointer-events:none） |
| .toast / .toast-region | 全局反馈（success/error/info，安全区置顶，自动消退） |
| .skeleton-* | 骨架屏 shimmer（reduced-motion 静止） |
| .message-day / .message-sender / .message-merged | 日期分组与连续消息合并 |
| .message-check / .select-bar | 消息多选与批量操作条 |
| .poll-card / .poll-option-* | 群投票卡片（百分比条、选中态、结束态） |
| .emoji-panel / .emoji-option | 输入框表情面板（分类网格） |
| .upload-progress-* | 上传进度条（含失败/重试态） |
| .image-viewer-* | 图片全屏查看器（深色遮罩） |
| .char-count | 输入剩余字数提示（接近上限/超限变红） |

## 页面模式

AuthShell（未登录）：居中 max-w-md 卡片（右上角主题切换 + 品牌标识 + slogan + 登录卡 + 底部
备案），登录外壳本身可内滚。

AppShell（已登录，微信式全高双栏）：`100dvh` 应用外壳、页面不滚动——顶部品牌栏（品牌 +
连接状态 + 个人菜单 + 主题切换）+ 双栏主区（会话列表栏 300px 内滚 + 聊天面板全高，消息列表
与输入框内部滚动，输入框固定在面板底部）+ 底部备案。整体 `max-width: 1200px`（紧凑密度
1160px）居中，消息/输入内容列 `max-width: 880px`（紧凑密度 840px）居中；移动端 <768px
单栏切换（列表 ↔ 聊天，返回按钮）；进入聊天时保留个人状态顶栏，聊天框全出血占满其下剩余
全屏、仅组件内滚动；顶栏与输入框适配 `env(safe-area-inset-*)`、隐藏页脚。品牌令牌
（信使蓝、中性色、圆角/阴影）不变。

密度策略：桌面端（≥768px）走紧凑密度层——按钮/图标钮/头像/气泡/间距整体收紧；移动端
（<768px）恢复 44px 触控热区与更宽松的消息排版，保证可点击性与可读性不降级。

新增组件一律复用品牌令牌（`--chat-*`）；全屏遮罩类（图片查看器/呼叫浮层）为固定深色，
语义色用 `color-mix` 派生，不引入新硬编码色板。

## 品牌单点

brand.js 暴露 `BRAND.{name,slug,slogan,description,icp,police,logo,footer()}`；页面禁止硬编码文案；Logo 为内联 SVG（两个方块细线相连 + 右侧光斑）。

## 氛围层

ambient.js 暴露 `LiChatAmbient.setDensity(n)`；浓度：登录 10、登录后 8、移动端（<768px）≤6；四类符号（直线穿行/方块钟摆/Z 形穿行/光斑公转）；颜色读 CSS 令牌；页面隐藏时暂停；reduced-motion 单帧。

## 验收状态

RGB 调校审计（2026-08-17，模板 V1.2 附录 E 方法）：模板原值四处不达 4.5，已同色相加深
落地（muted `#64736C`、success `#2A7C52`、warning `#9A5C05`、destructive `#CF3D3D`→
`#C43737`），调校后明暗两套文本/背景对全部 ≥4.5:1；主色 `#25786D` 保留原值（on soft
4.547）；深色软底带文字一律实色粉彩 + 深字（8–12:1），消息新到闪动改用 `primary-hover`
保证明暗两套可读。按钮状态纪律审计：现有异步动作的 pending 均为单按钮/消息气泡
spinner，无成对按钮双转圈。每个新增 `animation` 均已定义对应 `@keyframes`
（`chat-btn-sweep`、`chat-halo-breathe`），reduced-motion 下全局降为单帧。

布局回归（2026-08-16，微信式布局）：桌面 1440×900 与移动 390×844 经无头浏览器程序化验收——
页面 `scrollY=0`、`body overflow:hidden`、无横向溢出、聊天框内部滚动（可见高度 < 内容高度）、
桌面主区 ≤1200px / 内容列 ≤880px、移动端列表↔聊天切换正常、输入框未越出视口。

紧凑密度回归（2026-08-16）：桌面按钮 30–36px、图标钮 34px、头像 30px、气泡 14.7px、
头部 53px；移动端保留 44px 热区、气泡 15.2px；页面不滚/内滚/无横向溢出复验通过。

页面锁定复验（2026-08-16）：对 `window.scrollTo(0,99999)`、`documentElement/body.scrollTop`
强推滚动后 `scrollY/html/body scrollTop` 均为 0，`html/body overflow:hidden`；消息列表内滚
正常（`scrollTop` 可推进）；桌面与移动均无横向溢出。

移动端聊天全屏复验（2026-08-16，390×844）：保留状态顶栏（69px），聊天面板顶=69、高 775
（占满顶栏下剩余视口），输入框底=844 贴边；页面 `scrollY=0`，仅消息列表内滚。

移动端硬锁与输入框复验（2026-08-16）：`body` 固定定位 + `touch-action:none` 后强推滚动仍
为 0；输入框单行 44px → 三行 86px 自动增高（桌面 36 → 74px），发送/取消后复位。

Pre-Delivery Checklist 全部通过（2026-08-16 信使蓝版；2026-08-17 海玻璃配色全量换肤后
重验）：无 emoji 图标、可点击元素 cursor-pointer、hover 150–300ms、正文对比度 ≥4.5:1、
focus-visible 2px 主色描边、reduced-motion 单帧、375/1440 无横向滚动、令牌与文案无硬
编码、明暗切换无闪烁（首帧内联脚本 + 像素抽样验证：浅 `#F6FBF9` / 深 `#3A3F45`）。
视觉基线见 [preview/](./preview/)。
