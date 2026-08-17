# 实施计划：README 模板同步（2026-08-18）

> 分支：`codex/readme-template-sync` ｜ 依赖：[设计规格](../specs/2026-08-18-readme-template-sync-design.md)

## Task 1：同步子模块指针

- Consumes：`design-system/template`
- Produces：子模块指针 `745a7ef`

- [x] `git -C design-system/template fetch origin --prune`
- [x] `git -C design-system/template checkout 745a7ef`
- [x] `git add design-system/template`
- [x] 提交 `docs: 同步设计子模块至 745a7ef（README 模板新增）`

## Task 2：落地 README 模板规范

- Consumes：`README.md`、`AGENTS.md`、`CHANGELOG.md`
- Produces：上述文件更新 + 规格/计划文档

- [x] 写设计规格与实施计划
- [x] README：tagline + 徽章 + 目录 + 关于 + 仓库结构
- [x] AGENTS.md 第九节补充模板 README 参考
- [x] CHANGELOG 未发布区记录
- [x] 提交 `docs: 按 Li-Design README 模板落地（徽章/目录/关于）`

## Task 3：验证与收尾

- [x] `git submodule status` 显示 `745a7ef`
- [x] README 相对链接检查
- [x] `uv run pytest -q`（303 passed）/ `uv run ruff check .` / `uv run mypy app`
- [x] 合并回 `main`（保留 merge 记录）
