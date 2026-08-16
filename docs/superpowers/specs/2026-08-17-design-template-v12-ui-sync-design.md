# Li-Design 模板 V1.2 UI 同步设计规格

> 日期：2026-08-17 ｜ 状态：设计中 ｜ 分支：`codex/lipass-v2-sync`

## 1. 目标

拉取品牌设计子模块（Li-Design）更新（`909bcfb → 0010cda`，V1.2：海玻璃方案 + RGB 调校
方法），把对 Li&Chat 适用的通用增量同步到 `static/` 与 `design-system/chat/`，并明确
记录「不采用」项及理由。Li&Chat 自身品牌（信使蓝 V1.0）不整体切换为 Li&Pass 的海玻璃
配色。

## 2. 现状与事实

- 子模块 `design-system/template` 已指向 `0010cda`（经 ghproxy 复核 origin/main 最新，
  无更新提交可拉；指针已是远端最新）。
- Li&Chat 视觉事实来源为 `design-system/chat/BRAND.md` + `MASTER.md`，令牌在
  `static/style.css`、品牌单点在 `static/brand.js`；`template` 只作首次设计参考。
- 现按钮为主色纵向渐变实心块；认证卡无辉光；明暗两套令牌对比度已核算。

## 3. V1.2 增量与取舍

| 增量 | 决策 | 理由 |
| --- | --- | --- |
| RGB 色值调校方法（附录 E） | **采用（审计）** | 对现有令牌做对比度核算：全部 ≥4.5（最低 muted-on-bg 4.548），无需改色；结论回写 MASTER.md |
| 主按钮半透明单色着色 + 细描边 + `::after` 扫光 | **采用** | 槽位 22 新定稿按钮规范；信使蓝换算后文字对比 7.3（浅）/12.6（深），远超 4.5 |
| 认证卡辉光 `.card-halo`/`.brand-halo` | **采用（克制版）** | 信任优先的呼吸辉光，4.5s、reduced-motion 静止 |
| 按钮状态纪律（pending 只属于被点击按钮） | **审计后不修改** | 现实现单动作 spinner（消息气泡/上传浮层），无成对按钮双转圈 |
| 科技光效层（网格/光束/光点） | **不采用** | Li&Chat 已有定制 Canvas 氛围四模式；再叠网格/光束违背「克制」原则 |
| 深色雾灰中间调（不压黑） | **不采用** | 信使蓝深色 `#0B1220` 已定稿；属可选变体，维持原品牌 |
| 六强调色板（槽位 21） | **不采用令牌** | 单主色品牌无装饰性小面积用色需求，避免新增死色板 |
| secondary 角色令牌 | **不采用** | 「单一主色强调」是 Li&Chat 品牌内核，无第二主色场景 |

## 4. 令牌与组件变更（`static/style.css`）

- 新增按钮着色令牌（明暗两套）：`--chat-btn-primary-bg/-bg-hover/-border`、
  `--chat-brand-fg`；浅色文字 `#1E40AF`、深色文字 `#DBEAFE`。
- `.btn-primary` 改半透明底色 + 1px 同色描边 + `::after` 扫光（4s、`translateX`，
  `disabled` 关闭扫光）；保留 hover 抬升/按压态。
- 新增 `.auth-halo`（认证卡后浅主色呼吸辉光）与 `.brand-glow`（Logo 辉光），
  `pointer-events:none`、`aria-hidden`、reduced-motion 单帧。

## 5. 前端结构变更（`static/app.js`）

- `renderLoggedOut()` 认证卡增加 halo 包裹层，品牌 Logo 加 glow 类。
- 退出登录弹窗双动作（与 SSO 规格共用，见 `2026-08-17-lipass-v2-sso-sync-design.md`）。

## 6. 文档同步

- `design-system/chat/BRAND.md`：槽位表 20 → 22（新增 21/22 并填 Li&Chat 决策）、
  版本注记 V1.2 同步、记录不采用项与理由。
- `design-system/chat/MASTER.md`：令牌快照、组件清单（按钮/辉光）、验收状态
  （RGB 审计 4.5+ 全过、pending 审计无违规）。

## 7. 验收标准

- [ ] 新旧按钮对比：半透明着色 + 描边 + 扫光生效，disabled 无扫光
- [ ] 认证卡辉光在明暗两套下可见但克制，reduced-motion 静止
- [ ] 令牌对比度核算 ≥4.5（按钮文字对底色 ≥4.5）
- [ ] 每个 `animation` 均有对应 `@keyframes`
- [ ] `pytest -q` / `ruff check .` / `mypy app` 全绿
- [ ] 浏览器视觉冒烟截图存档 `design-system/chat/preview/`
