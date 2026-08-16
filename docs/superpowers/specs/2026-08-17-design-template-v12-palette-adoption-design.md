# Li-Design V1.2 配色方案全量采纳设计规格（补遗）

> 日期：2026-08-17 ｜ 状态：设计中 ｜ 分支：`codex/lipass-palette-sync`
> 前序规格：`2026-08-17-design-template-v12-ui-sync-design.md`（本次按用户指令修订其
> 「不采用」决策：配色方案改为全量采纳）

## 1. 目标

用户明确要求「同时使用设计子模块的配色方案」：Li&Chat 全面切换到
`design-system/template` V1.2 的**海玻璃全淡色系**（浅色）与 **D1 雾灰中间调**（深色），
含 second/六强调色板、按钮着色令牌与 tint 阴影。同时复核账号身份绑定：仅 `sub` 是
唯一可信标识，`email` 是可变属性。

## 2. 取值（以 `reusable-tokens.template.css` 为令牌事实）

| 组 | 浅色 | 深色 |
| --- | --- | --- |
| 中性 | bg `#F6FBF9` / surface `#FFF` / surface-2 `#EEF6F3` / fg `#35423F` / border `#E1ECE8` | bg `#3A3F45` / surface `#434950` / surface-2 `#4B5259` / fg `#F0F2F4` / border `#545C64` |
| 主色 | `#25786D` / hover `#1F6359` / soft `#D9F4EE` / fg `#FFF` | `#7FD4C6` / hover `#A5E4D9` / soft `rgba(127,212,198,.16)` / fg `#17332E` |
| secondary | `#2F678F` / soft `#DFF1FA` | `#A8D4F0` / soft `rgba(168,212,240,.16)` |
| 语义 | 见 §3 调校值 | 见 §3 |
| 强调色 | ice `#2F678F`/aqua `#25786D`/lilac `#51488F`/sage `#557546`/mint `#2F7C52`/sand `#876741` + soft | `#A8CBE8`/`#7FD4C6`/`#B0A8DE`/`#B0C79E`/`#9ADFAD`/`#D9C49E` + soft rgba |
| 按钮 | bg `rgba(47,127,116,.10)` / hover `.17` / 描边 `.26` / 文字 `#24433E` | bg `rgba(127,212,198,.13)` / hover `.21` / 描边 `.30` / 文字 `#D7EFEA` |
| ring / 阴影 | `#25786D` / 水绿 tint `rgba(24,58,51,*)` | `#7FD4C6` |

科技光效层（网格/光束/光点）与流光线属于**光效风格**而非配色，继续不采用；其专属令牌
（tech-*）不落地。品牌名/Logo/字体/氛围四模式不变。

## 3. RGB 调校（模板附录 E：正文/strong-on-soft ≥ 4.5:1）

模板原值直接落地时四处不达标，按同色相加深、保持雾面感（S 不变/略降）调校：

| 令牌 | 模板原值 | 落地值 | 理由 |
| --- | --- | --- | --- |
| muted（浅） | `#71807A` | `#64736C` | 原值 on bg 3.96、on white 4.14 |
| success（浅） | `#2F8F5F` | `#2A7C52` | 原值 on bg 3.85、on soft 3.57 |
| warning（浅） | `#A16207` | `#9A5C05` | 原值 on soft 4.45 |
| destructive（浅） | `#CF3D3D` | `#C43737` | 原值 on soft 4.25 |

主色 `#25786D` 保留原值（on soft 4.547 压线通过，不偏离模板品牌主色）。

深色软底（模板附录 E 铁律：`rgba(浅色,0.14–0.18)` 软底上同色浅字上限 ≈3.9，不可 4.5）：
带文字的场景改用**实色粉彩底 + 深色文字**，新增深色令牌并在组件用 fallback 引用：

```css
.dark {
  --chat-primary-soft-solid: #d9f4ee;   --chat-primary-soft-fg: #17332e;
  --chat-success-soft-solid: #e3f6e9;   --chat-success-soft-fg: #14532d;
  --chat-warning-soft-solid: #fdf3d8;   --chat-warning-soft-fg: #78350f;
  --chat-destructive-soft-solid: #fdeeee; --chat-destructive-soft-fg: #7f1d1d;
}
/* 组件：background: var(--chat-primary-soft-solid, var(--chat-primary-soft));
          color: var(--chat-primary-soft-fg, var(--chat-primary)); */
```

涉及组件：`.badge-success/warning/danger/primary`、`.reaction-chip-active`、
`.group-avatar`、`.voice-recording`、`.message-failed`（+`-text`）、`.message-flash`。

## 4. 身份绑定审计（sub 唯一可信，email 可变）

- 事实：`users.sub` 为唯一主键；`upsert_user` 按 `sub` 查找、每次登录刷新
  `email/email_verified/name`，邮箱无唯一约束、不参与任何鉴权查找。
- 动作：补测试证明「同 sub 换 email 不新建用户、只刷新属性」；docs/oidc-integration.md
  与 docs/security.md 写明绑定规则。

## 5. 验收标准

- [ ] `static/style.css` 令牌与上表一致；`test_frontend.py` 断言同步新主色
- [ ] 明暗两套关键文本对比 ≥4.5（含 badge/徽章等 soft 底组合，核算脚本输出存档）
- [ ] index.html/theme.js/ambient.js 品牌位与回退色同步
- [ ] sub/email 绑定测试通过
- [ ] `pytest -q` / `ruff check .` / `mypy app` 全绿
- [ ] CDP 视觉断言（新配色明暗两套）全过，六张预览重拍
