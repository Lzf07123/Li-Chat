# Li-Design 子模块 README 模板同步设计规格

> 日期：2026-08-18 ｜ 状态：已定稿 ｜ 分支：`codex/readme-template-sync`

## 1. 目标

同步设计子模块 `design-system/template` 至远端最新提交 `745a7ef`（README 模板新增），
并按子模块更新把对 Li&Chat 适用的对应内容落地到项目 README 与相关文档。

## 2. 现状与事实

- 子模块此前锁定 `0010cda`（V1.2 海玻璃 + RGB 调校）；本次远端增量仅三个提交：
  - `3e92b93`：新增 `reusable-readme.template.md`（Li&About 规范 README 模板）
  - `dc91baf`：README 模板徽章改为默认 flat 样式
  - `b5bc93c`：README 模板同步徽章平铺与技能边界规则
- `REUSABLE-BRAND-SCHEME.md` 与 `reusable-tokens.template.css` 无变化，设计令牌不涉及改动。
- Li&Chat README 目前无顶部徽章、无目录、无「关于」信息表；「项目结构」小节名与模板
  「仓库结构」不一致。

## 3. 增量与取舍

| 增量 | 决策 | 理由 |
| --- | --- | --- |
| 顶部徽章（状态/角色/方向 + 技术徽章，flat 平铺） | **采用** | 项目 README 无徽章，按模板补状态/角色/方向与真实技术徽章，技术徽章链接官网 |
| 目录 | **采用** | README 超百行，按模板启用锚点目录 |
| 关于信息表（身份/方向/方式/目标） | **采用** | 与模板「关于」板块对齐，信息均来自 BRAND.md 槽位 |
| 「仓库结构」小节名 | **采用** | 与模板结构约定一致，内容不变 |
| 技能栈 / 项目 / 当前目标 / 许可 | **不采用** | 面向个人主页与多项目列表；项目 README 已用功能/快速开始/质量门禁/文档索引替代，且无许可信息，不留空占位 |

## 4. 文件变更

- `design-system/template`：指针 `0010cda → 745a7ef`
- `README.md`：tagline、徽章、目录、关于、仓库结构
- `AGENTS.md`：第九节补充 README 模板参考
- `CHANGELOG.md`：未发布区记录
- `docs/superpowers/specs/2026-08-18-readme-template-sync-design.md`：本规格
- `docs/superpowers/plans/2026-08-18-readme-template-sync.md`：实施计划

## 5. 验收标准

- [ ] `git submodule status` 显示 `745a7ef`
- [ ] README 顶部徽章为 flat 样式、技术徽章链接官网、平铺不分组
- [ ] README 目录锚点与标题一致
- [ ] 本地相对链接全部可解析
- [ ] `pytest -q` / `ruff check .` / `mypy app` 全绿
