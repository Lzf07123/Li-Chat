# Li-Design V1.2 页面特效层采纳设计规格（补遗二）

> 日期：2026-08-17 ｜ 状态：设计中 ｜ 分支：`codex/lipass-effects-sync`
> 前序规格：`...-palette-adoption-design.md`（其「科技光效层不采用」决策按本次用户指令修订：
> 页面特效层一并采纳）

## 1. 目标

在已采纳的海玻璃配色之上，补上 Li-Design V1.2 的**页面特效层**：极光层（AuroraBackground，
4 枚弥散光斑）+ 科技光效层（TechAmbience，缓移网格 + 3 条错峰光束 + 8 枚呼吸光点）。
与既有 Canvas 氛围四模式叠加，构成模板的三层氛围栈；纯 CSS 实现、零第三方依赖。

## 2. 参数（模板 §2.4.1 / 组件表定稿值）

| 层 | 元素 | 节奏 |
| --- | --- | --- |
| 极光 | 4 枚光斑，radial-gradient 软斑（不用 filter/blur），transform 漂移 + scale | 18/22/28/24s，alternate |
| 科技网格 | 56px 基线 + 336px 亮线双层 repeating-gradient + 径向渐隐遮罩，`background-position` 漂移 336px（6 格，无缝） | 12s linear infinite |
| 科技光束 | 斜切 16° 透明渐变带，`translateX` 扫过并长停顿；基态 opacity 0 | 10s，错峰 0.8/4.2/7.5s |
| 科技光点 | 7px 圆点 + radial 辉光（无 box-shadow/filter），opacity/transform 脉动 + 上浮 | 6s，8 枚错峰 |

## 3. 结构

- `static/index.html`：`<body>` 顶部新增 `.aurora`（4×`.aurora-blob`）与
  `.tech-ambience`（`.tech-grid` + 3×`.tech-beam` + 8×`.tech-dot`），`aria-hidden`。
- 层级：极光/科技层 `position:fixed; z-index:0`，位于 `#app`（z-1）之下；Canvas 氛围层
  仍在最上（DOM 末尾追加）。所有层 `pointer-events:none`。
- `static/app.js` `mount()`：登录后外壳给两特效容器加 `aurora-soft`/`tech-soft`
  （整体 opacity 0.55 降浓度）；认证页默认浓度。

## 4. 铁律落地

- 只动 `transform/opacity/background-position`；辉光用 radial-gradient，禁用
  `filter/box-shadow` 动画；每个 `animation` 都有对应 `@keyframes`。
- 移动端（<768px）：隐藏光束/光点、停用网格动画、极光更慢更淡。
- `prefers-reduced-motion`：全局既有规则降为单帧（光束基态不可见即静止关闭）。

## 5. 验收标准

- [ ] 认证页：网格/光束/光点/极光四个 animation 计算值与 `@keyframes` 一一对应
- [ ] 登录后外壳：`.tech-soft`/`.aurora-soft` 生效，opacity 0.55
- [ ] 移动端 375：光束/光点 `display:none`、网格动画 none
- [ ] `pytest -q` / `ruff check .` / `mypy app` 全绿；CDP 断言全过；六张预览重拍
