# Li&Chat IM 路线图 v2 实施计划：在线状态与正在输入

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/models.py`、`app/main.py`、`app/ws/manager.py`、`app/friends/service.py`、
  `app/api/friends.py`、`static/app.js`、`static/style.css`、`docs/api.md`、
  `docs/architecture.md`、`CHANGELOG.md`
- Produces：`users.last_seen_at` 与 SQLite 兼容迁移、presence 广播（仅好友）、typing
  中继（好友校验 + 2 秒限频）、`GET /api/friends` 附 online/last_seen_at、前端在线圆点与
  正在输入提示、`tests/test_presence.py`

## 步骤（TDD）

- [x] 写失败测试：上线/下线事件仅好友可见、断线写 last_seen_at、friends 附在线字段、
  typing 定向中继、限频
- [x] 实现 `ConnectionManager.has/count/typing_allowed`
- [x] 实现 main.py：连接广播 presence、断开回写 last_seen_at 并广播、typing 中继
- [x] 实现 `users.last_seen_at` + `_ensure_user_columns`；friends 接口附 online/last_seen_at
- [x] 前端：好友/会话在线圆点、正在输入发送与展示
- [x] 全量验证 pytest / ruff / mypy 全绿（131 通过）
- [x] 独立提交 `feat: 在线状态与正在输入（presence + typing）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md

## 验收

见规格 v2 验收清单；门禁输出与 `git show --stat` 作为证据。
