# Li&Chat IM 路线图 v4 实施计划：表情回应

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/models.py`、`app/messages/service.py`、`app/api/messages.py`、
  `static/app.js`、`static/style.css`、`docs/api.md`、`docs/architecture.md`、
  `docs/security.md`、`CHANGELOG.md`
- Produces：`reactions` 表、`PUT/DELETE /api/conversations/{sub}/messages/{id}/reactions`、
  历史消息附 `reactions` 聚合与 `my_reaction`、WS `message_reaction`、前端回应栏与快捷
  emoji、`tests/test_reactions.py`

## 步骤（TDD）

- [x] 写失败测试：幂等增/删、聚合计数、非参与者 404、非法 emoji 422、已撤回 409、WS 事件
- [x] 模型 `Reaction`；service：emoji 校验、set_reaction、reactions_for 批量聚合
- [x] 路由（PUT/DELETE + query emoji）与 WS `message_reaction`；history 附聚合
- [x] 前端：回应栏、快捷 emoji 选择、点击切换、WS 增量更新
- [x] 全量验证 pytest / ruff / mypy 全绿（140 通过）
- [x] 独立提交 `feat: 表情回应（幂等 toggle + 聚合回显）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md / docs/security.md

## 验收

见规格 v4 验收清单；门禁输出与 `git show --stat` 作为证据。
