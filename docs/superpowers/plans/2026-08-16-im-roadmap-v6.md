# Li&Chat IM 路线图 v6 实施计划：群消息与群已读（会话抽象迁移）

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/models.py`、`app/main.py`、`app/messages/service.py`、
  `app/api/groups.py`、`static/app.js`、`static/style.css`、`docs/api.md`、
  `docs/architecture.md`、`docs/security.md`、`docs/deployment.md`、`CHANGELOG.md`
- Produces：`messages.conversation_type/group_id` 与 recipient 可空迁移（SQLite 重建兼容
  旧库）、`group_reads` 表、群发送/历史/已读路由、`GET /api/conversations` 合并群摘要、
  WS 群消息与群已读回执、前端群聊天与群未读徽标、`tests/test_group_messages.py`、
  `tests/test_migrations.py`

## 步骤（TDD）

- [x] 写失败测试：群发送/历史/分页/非成员 403/404、群未读与已读、摘要合并、WS 广播、
  SQLite 旧库迁移
- [x] 模型迁移（conversation_type/group_id + `group:{id}` 哨兵，零重建）与
  `_ensure_message_columns` 补列逻辑
- [x] service：群发送/历史/已读 + 会话摘要合并
- [x] 路由与 WS 事件；前端群聊天/群未读
- [x] 全量验证 pytest / ruff / mypy 全绿（152 通过）
- [x] 独立提交 `feat: 群消息与群已读（会话抽象迁移）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md / docs/security.md /
  docs/deployment.md

## 验收

见规格 v6 验收清单；门禁输出与 `git show --stat` 作为证据。
