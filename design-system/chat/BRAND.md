# Li&Chat · 品牌 UI 设计报告

> **版本**：V1.2 ｜ **日期**：2026-08-17 ｜ **状态**：已发布（后续统一风格以本文件为准）
> **模板同步**：槽位 20 → 22、主按钮半透明着色 + 扫光、认证卡辉光落地；按用户指令**全量
> 采纳 Li-Design 模板 V1.2 海玻璃配色方案**（浅色全淡色 + 深色雾灰中间调 + 强调色板）。
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

主色 = 海玻璃 `#25786D`（浅）/ `#7FD4C6`（深），全淡色、无粉色、无大面积重色
（Li-Design 模板 V1.2 定稿口径，见设计规格 `2026-08-17-design-template-v12-palette-adoption-design.md`）。

浅色：bg `#F6FBF9` / surface `#FFFFFF` / surface-2 `#EEF6F3` / fg `#35423F` / muted `#64736C` / border `#E1ECE8`；primary `#25786D` hover `#1F6359` soft `#D9F4EE` fg `#FFFFFF`；secondary `#2F678F` / soft `#DFF1FA`；success `#2A7C52` / warning `#9A5C05` / destructive `#C43737` 及 soft；ring `#25786D`。

深色（D1 雾灰，不压黑）：bg `#3A3F45` / surface `#434950` / surface-2 `#4B5259` / fg `#F0F2F4` / muted `#B8C0C7` / border `#545C64`；primary `#7FD4C6` hover `#A5E4D9` soft `rgba(127,212,198,0.16)` fg `#17332E`；secondary `#A8D4F0` / soft `rgba(168,212,240,0.16)`；success `#86D6AC` / warning `#EAD48E` / destructive `#E8A49A`；ring `#7FD4C6`。

用色比例 60/30/10；主色永远小面积强调；语义色只表达状态。

按模板附录 E 做 RGB 调校：模板原值四处不达 4.5 已同色相加深（muted→`#64736C`、
success→`#2A7C52`、warning→`#9A5C05`、destructive→`#C43737`）；深色带文字的软底一律
实色粉彩底 + 深字（`*-soft-solid`/`*-soft-fg` 令牌），不得用 rgba 软底配同色浅字。

### 3.2 字体与排版

字体栈 Inter → 系统栈 → PingFang SC / 微软雅黑，不加载远程字体；正文 16px/1.5；暂不引入标题字体（零外部依赖，后续如需要自托管 subset）。

### 3.3 形状、间距与层次

按钮/输入框 8px 圆角，卡片 16px，徽章 999px；间距 4px 刻度，卡片内边距 24px 起步；三档弥散阴影透明度总和 <0.1；层级：氛围层 z-0 < 内容 z-1 < 顶栏 z-20。

### 3.4 Logo 与图标

Logo 为家族几何语法 SVG 标识「两个方块以细线相连、右上方带光斑」（对话 + 在线），单源定义于 brand.js，favicon 用同形 SVG；图标一律内联 SVG（24 viewBox、2px 描边、圆角端点、currentColor），禁止 emoji。

## 4. 氛围动效（呼吸感四模式）

符号隐喻：直线=消息通路、Z 形=对话往返、方块=消息、光斑=在线状态；锁钥仅在信任关键时刻出现，不在背景层使用。

浓度：登录页 10、登录后 8；移动端（<768px）≤6 且更慢更淡；prefers-reduced-motion 下绘制静态单帧；元素 pointer-events:none、永远在内容层之下。

页面特效层（模板 V1.2，与 Canvas 氛围叠加）：极光层 4 枚弥散光斑（18/22/28/24s 漂移，
radial-gradient 软斑、无 filter）；科技光效层 = 缓移网格（56px/336px 双层，12s 无缝
漂移）+ 3 条斜切光束（10s，错峰 0.8/4.2/7.5s，基态透明）+ 8 枚呼吸光点（6s 错峰）。
认证页默认浓度、登录后 `.tech-soft`/`.aurora-soft` 降为 0.55；移动端隐藏光束/光点、
停用网格动画、极光更慢；reduced-motion 单帧。铁律：只动
`transform/opacity/background-position`，每个 animation 都有 @keyframes。

全量采纳（2026-08-17，模板提及的其余项）：认证卡签名描边（`.card-signature` 流色渐变环
9s，替换静态边框）、顶栏流光线（`.flow-line` 5s）、按钮涟漪（`.btn-ripple` 500ms，
currentColor）、文字浮现（`.blur-unit` 词级 blur+位移入场 450ms、35ms 错峰）、数字滚动
（`countUp` 三次缓动 450ms，未读/申请/归档徽章变化时动画）、表单聚焦联动（`.is-typing`
下氛围周期 ×2）、滚动联动（scroll wind 0.5x–1.5x 并衰减回 1）。第三方依赖项（BlurText/
CountUp 的 motion/react、gsap 组件）一律以零依赖等价实现，维持「不加载远程资源」底线。

## 5. 文案语调

清晰优先、动词开头按钮、不用感叹号、错误可行动、安全语言诚实但不吓唬、数字与时间精确。

## 6. 治理

四级分层：BRAND.md（意图）→ MASTER.md（快照）→ style.css / brand.js（代码事实）→ 页面。冲突时以代码为准并回写文档。

Li-Design 模板 V1.2（2026-08-17）：先同步按钮/辉光规范，后按用户指令**全量采纳海玻璃
配色方案**（浅色全淡色、深色雾灰、secondary 与六强调色板、按钮着色令牌、tint 阴影）；
落地时按模板附录 E 做 RGB 调校（四处同色相加深 + 深色软底实色粉彩/深字）。随后按用户
指令补上页面特效层（极光 + 科技光效），最终把模板提及的流光线、卡片签名描边、按钮涟漪、
文字浮现、数字滚动、聚焦/滚动联动全部以零依赖方式落地；仅表格/标签页/Bento（gsap 组件、
无使用场景）与 Lexend 自托管字体（需先交付字体资产）暂缓。取舍记录见槽位 21/22 与设计规格
`docs/superpowers/specs/2026-08-17-design-template-v12-all-adoption-design.md`。

## 7. 槽位表

| # | 槽位 | 取值 |
| --- | --- | --- |
| 1 | 项目显示名 | `Li&Chat` |
| 2 | 技术标识 | 基础设施 `lichat`；项目 slug 与 CSS 前缀 `chat` |
| 3 | 一句话定位 | 一次登录，直连你的小圈子 |
| 4 | 品牌承诺 | 对话只在你们之间流动；每一次登录都经 Li&Pass 验证 |
| 5 | 人格比喻 | 可靠的信使：准确送达、不多嘴、不打扰 |
| 6 | 符号隐喻 | 直线=消息通路、Z 形=对话往返、方块=消息、锁钥=私密、光斑=在线状态 |
| 7 | 主色（浅） | `#25786D` / hover `#1F6359` / soft `#D9F4EE` / fg `#FFFFFF`（海玻璃，模板 V1.2 定稿） |
| 8 | 主色（深） | `#7FD4C6` / hover `#A5E4D9` / soft `rgba(127,212,198,0.16)` / fg `#17332E` |
| 9 | 中性色（浅） | `#F6FBF9` / `#FFFFFF` / `#EEF6F3` / `#35423F` / `#64736C` / `#E1ECE8`（muted 经 RGB 调校） |
| 10 | 中性色（深） | `#3A3F45` / `#434950` / `#4B5259` / `#F0F2F4` / `#B8C0C7` / `#545C64`（D1 雾灰，不压黑） |
| 11 | 语义色 | 浅：success `#2A7C52`、warning `#9A5C05`、destructive `#C43737` 及 soft（RGB 调校）；深：`#86D6AC` / `#EAD48E` / `#E8A49A` 及 rgba soft + 实色粉彩 soft-solid/soft-fg |
| 12 | 焦点环 | 浅 `#25786D`、深 `#7FD4C6`，2px 描边 + 2px offset，`focus-visible` 全局 |
| 13 | 字体栈 | Inter → 系统栈 → PingFang SC / 微软雅黑；不加载远程字体 |
| 14 | 标题字体 | 暂不引入 Lexend（零外部依赖）；后续如需自托管 subset 再议 |
| 15 | Logo / favicon | 几何标识「两个方块细线相连 + 右侧光斑」，内联 SVG + `favicon.svg`，透明底、无位图 |
| 16 | 令牌前缀 | `chat`（`--chat-bg` 等） |
| 17 | 主题存储键 | `chat-theme` |
| 18 | slogan / 备案 | slogan「一次登录，直连你的小圈子」；备案上线前留空，禁止假占位号 |
| 19 | 氛围浓度 | Canvas：认证页 10、登录后 8；移动端（<768px）≤6。特效层：极光 + 科技光效认证页默认、登录后 soft；移动端隐藏光束/光点并停网格 |
| 20 | 浏览器品牌位 | `favicon.svg`、`theme-color`（浅 `#F6FBF9` / 深 `#3A3F45`）、description、首帧主题脚本 |
| 21 | 强调色板 | 六色相 strong/soft（浅：ice `#2F678F`/aqua `#25786D`/lilac `#51488F`/sage `#557546`/mint `#2F7C52`/sand `#876741`；深：`#A8CBE8`/`#7FD4C6`/`#B0A8DE`/`#B0C79E`/`#9ADFAD`/`#D9C49E`），令牌已落地、暂未接装饰位（合计 ≤15% 可视面积铁律） |
| 22 | 按钮与光效风格 | 主按钮半透明单色着色（浅 `rgba(47,127,116,.10)` / 深 `rgba(127,212,198,.13)` + 同色细描边）+ `::after` 扫光 4s + `.btn-ripple` 涟漪 500ms，文字浅 `#24433E` / 深 `#D7EFEA`；认证卡/Logo 呼吸辉光 4.5s、认证卡签名描边 9s、顶栏流光线 5s；**极光层 + 科技光效层（网格/光束/光点）已采纳**（参数见 §4）。深色采用 D1 雾灰中间调；表格/标签页/Bento/Lexend 暂缓（gsap 或字体资产依赖） |
