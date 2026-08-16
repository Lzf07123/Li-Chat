# Li&Chat IM 路线图 v5 实施计划：群聊管理

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/models.py`、`app/main.py`、`app/friends/service.py`、`static/app.js`、
  `static/style.css`、`docs/api.md`、`docs/architecture.md`、`docs/security.md`、
  `CHANGELOG.md`
- Produces：`groups`/`group_members` 表、`app/groups/service.py`、`app/api/groups.py`、
  群角色权限矩阵、WS `group_event`、前端群列表/详情/成员管理、`tests/test_groups.py`

## 步骤（TDD）

- [x] 写失败测试：建群/邀请非好友 403/角色矩阵/移除规则/转让/退出/非成员不可见/WS 事件
- [x] 模型与 service（create/list/get/rename/add/remove/leave/transfer/set_role）
- [x] 路由挂载与 WS `group_event`（受影响成员广播）
- [x] 前端：侧栏群分组、建群弹层、群详情与成员操作
- [x] 全量验证 pytest / ruff / mypy 全绿（146 通过）
- [x] 独立提交 `feat: 群聊管理（建群/成员/角色矩阵）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md / docs/security.md

## 验收

见规格 v5 验收清单；门禁输出与 `git show --stat` 作为证据。
