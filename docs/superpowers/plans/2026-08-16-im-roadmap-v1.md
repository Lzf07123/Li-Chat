# Li&Chat IM 路线图 v1 实施计划：未读计数与已读回执

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/models.py`、`app/messages/service.py`、`app/api/messages.py`、
  `app/main.py`（路由挂载沿用）、`static/app.js`、`static/style.css`、`docs/api.md`、
  `docs/architecture.md`、`CHANGELOG.md`、`tests/test_messages.py`
- Produces：`dm_reads` 模型、会话摘要与已读 service、`GET /api/conversations`、
  `POST /api/conversations/{other_sub}/read`、WS `read_receipt`、前端未读徽标与已读指示、
  测试 `tests/test_unread.py`

## 步骤（TDD）

- [x] 写失败测试：未读累计/清零、游标单调、非好友 403、会话摘要排序与字段、WS 回执
- [x] 实现 `DmRead` 模型与 `_ensure` 无关（新表由 create_all 覆盖；旧库无此表无迁移负担）
- [x] 实现 service：`conversation_summaries` / `mark_read` / 发送时推进发送者游标
- [x] 实现路由与 WS `read_receipt`；`/api/conversations` 摘要契约
- [x] 前端：好友栏未读徽标 + 打开会话即标记已读 + 已读回执指示 + 按最后消息排序
- [x] 全量验证：pytest / ruff / mypy 全绿（126 通过）
- [x] 独立提交 `feat: 未读计数与已读回执（会话列表 + WS 回执）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md

## 验收

见规格 v1 验收清单；`git show --stat` 与门禁输出作为证据。
