# Li-Design V1.2 全量采纳设计规格（补遗三）

> 日期：2026-08-17 ｜ 状态：设计中 ｜ 分支：`codex/lipass-all-sync`
> 前序：`...-effects-adoption-design.md`。本次按用户指令「使用设计子模块中提到的所有」，
> 把模板提及的其余组件/动效全部落地（第三方依赖项以零依赖等价实现）。

## 1. 采纳清单（新增）

| 模板项 | 落地方式 | 参数 |
| --- | --- | --- |
| 卡片签名描边（.card-signature） | 认证卡 `::after` mask 环 + `--chat-flow-gradient`，替换静态边框 | 9s、300% 背景位无缝循环 |
| 流光线（顶栏流光规则线） | `.flow-line` 置于 `.app-header` 底部 | 5s、300% 位移动 |
| 按钮涟漪 `.btn-ripple` | 全局事件委托 + `currentColor` 波纹，`animationend` 移除 | 500ms |
| 文字浮现 BlurText | 零依赖等价：`blurText()` 按词/字拆 `span.blur-unit`，blur+位移入场（认证页 h1/品牌名） | 450ms、错峰 35ms/字 |
| 数字滚动 CountUp | 零依赖等价：`countUp()` 三次缓动；未读/申请/归档徽章按变化动画 | 450ms |
| 表单聚焦联动 `.is-typing` | ambient.js 监听 input/textarea 焦点，氛围周期 ×2（速度减半） | — |
| 滚动联动（scroll wind） | ambient.js 捕获滚动，0.5x–1.5x 风速 + 向 1 衰减 | 0.5–1.5x |
| `--ease-in` 令牌 / `.input-sm` | 令牌与紧凑输入框组件补齐 | 150/250/350ms |
| PageSkeleton / spinner | 已有 `.skeleton-*` / `.spinner`（不重复实现） | — |

## 2. 不采纳项（附理由，记录于 BRAND.md）

- 表格 `.table-shell`、标签栏 ScrollTabs/PillTabs、MagicBento、StrokeText：Li&Chat 无表格/
  标签页/Bento 使用场景，且模板明示 gsap 依赖「按需引入」；维持零依赖品牌底线。
- Lexend 标题字体（槽位 14）：自托管 subset 需先交付字体资产与子集化决策，暂缓（槽位已记录）。

## 3. 铁律

- 新增动效只动 `transform/opacity/background-position`；BlurText 入场例外允许
  `filter: blur()`（一次性入场，reduced-motion 直接落定最终态）。
- 每个 `animation` 都有 `@keyframes`；reduced-motion 下 BlurText/涟漪直接到达最终态。
- 涟漪/流光线/签名描边 `pointer-events:none`，不阻塞交互。

## 4. 验收标准

- [ ] 认证卡签名描边、顶栏流光线、按钮涟漪、BlurText、CountUp、is-typing、scroll wind 全部生效
- [ ] `pytest -q` / `ruff check .` / `mypy app` 全绿；静态契约测试覆盖新组件
- [ ] CDP 断言：签名描边/流光线/涟漪动画名、blur-unit 存在、聚焦后 `.is-typing`、点按产生 `.btn-ripple`
- [ ] 六张预览重拍（含签名描边与流光线）
