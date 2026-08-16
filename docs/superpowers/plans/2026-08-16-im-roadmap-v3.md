# Li&Chat IM 路线图 v3 实施计划：消息编辑与撤回

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/models.py`、`app/main.py`、`app/messages/service.py`、`app/api/messages.py`、
  `static/app.js`、`static/style.css`、`docs/api.md`、`docs/architecture.md`、
  `docs/security.md`、`CHANGELOG.md`、`tests/test_messages.py`
- Produces：`messages.edited_at/deleted_at` + SQLite 兼容迁移、`PATCH/DELETE
  /api/conversations/{sub}/messages/{id}`、WS `message_edited/message_deleted`、
  历史墓碑（不泄露原文）、前端编辑/撤回交互、`tests/test_message_actions.py`

## 步骤（TDD）

- [x] 写失败测试：编辑成功/越权/超窗/空白 422、撤回墓碑不泄露原文、重复操作 409、WS 事件
- [x] 模型加 `edited_at/deleted_at` + `_ensure_message_columns` 兼容迁移
- [x] service：`edit_message/delete_message`（发送者、5 分钟窗、撤回清空 content）
- [x] 路由与 WS 事件；`MessageOut` 支持 deleted/edited_at/content 可空
- [x] 前端：撤回/编辑按钮、编辑态提交、墓碑与已编辑展示、侧栏预览适配
- [x] 全量验证 pytest / ruff / mypy 全绿（135 通过）
- [x] 独立提交 `feat: 消息编辑与撤回（5 分钟窗口）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md / docs/security.md

## 验收

见规格 v3 验收清单；门禁输出与 `git show --stat` 作为证据。
